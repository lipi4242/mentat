/**
 * /api/* → forwarded to the mentat-admin-api worker, from the same origin.
 *
 * WHY: the sign-in cookie is `SameSite=Lax`, so the browser will NOT send it
 * if the admin UI and the API sit on separate schemes/domains (pages.dev ↔
 * workers.dev). This proxy makes the two look like one origin: the browser
 * only ever talks to the admin domain, the cookie lands there, and sign-in
 * works even before custom domains (admin./api.<instance>) go live.
 *
 * The target is the `API_ORIGIN` Pages variable (e.g. the worker's
 * workers.dev URL). It is instance data, so there is no default here: an
 * unset variable answers 500 with a clear message instead of forwarding the
 * sign-in cookie to some other installation's API. Set it once per Pages
 * project: `npx wrangler pages secret put API_ORIGIN --project-name=<name>`.
 * Stays correct after any DNS cutover too — it just stops being required.
 */
interface Env {
  API_ORIGIN?: string;
}

export const onRequest: PagesFunction<Env> = async (ctx) => {
  const origin = ctx.env.API_ORIGIN?.trim();
  if (!origin) {
    return Response.json({ error: 'API_ORIGIN not configured on this Pages project' }, { status: 500 });
  }
  const incoming = new URL(ctx.request.url);
  const target = new URL(incoming.pathname + incoming.search, origin);

  // The Request copy carries the method, headers (including Cookie), and
  // body; fetch rewrites the Host header to match the target. `redirect:
  // 'manual'` so any redirect is seen by the browser rather than followed
  // here on the server.
  const proxied = new Request(target, ctx.request);
  proxied.headers.delete('host');

  const res = await fetch(proxied, { redirect: 'manual' });

  // A fresh Response so headers (including Set-Cookie) can be read/modified
  // — the original is immutable. Copying a Headers object preserves repeated
  // `Set-Cookie` entries (verified against workerd via `wrangler pages dev`);
  // collapsing them would drop a cookie and break sign-in.
  const headers = new Headers(res.headers);

  // A redirect back to the API's own origin would send the browser off the
  // admin domain — and the SameSite=Lax cookie this proxy exists to keep
  // same-origin would then be set on the wrong host. Rewrite it to a
  // same-origin path; leave third-party redirects alone.
  const location = headers.get('location');
  if (location) {
    const abs = new URL(location, target);
    if (abs.origin === target.origin) headers.set('location', abs.pathname + abs.search + abs.hash);
  }

  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
};

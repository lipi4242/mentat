import type { I18nProvider } from '@refinedev/core';

/**
 * Hungarian overrides for the handful of strings Refine renders itself.
 *
 * Everything the app writes is already Hungarian (resource `meta.label`,
 * page copy) and antd's own chrome comes from `locale={huHU}` in App.tsx.
 * What was left in English was Refine's own sider logout item.
 *
 * Deliberately NOT a full translation catalogue. `useTranslate` in
 * @refinedev/core resolves as:
 *
 *   i18nProvider.translate(key, options, defaultMessage)
 *     ?? defaultMessage
 *     ?? (typeof options === 'string' && defaultMessage === undefined ? options : key)
 *
 * so returning `undefined` for an unknown key hands the string straight back
 * to Refine's own fallback chain — byte for byte what renders with no
 * i18nProvider at all. A catalogue that returned the key instead would blank
 * or mangle every Refine label the moment one went missing.
 */
const HU: Record<string, string> = {
  'buttons.logout': 'Kijelentkezés',
};

export const i18nProvider: I18nProvider = {
  // The declared return type is `string`, but returning undefined is the
  // documented-above fallback path — see the resolution chain in the comment.
  translate: (key: string) => HU[key],
  changeLocale: () => Promise.resolve(),
  getLocale: () => 'hu',
};

// ULID (https://github.com/ulid/spec): 48-bit ms timestamp + 80 random bits,
// Crockford base32. The writer makes the id, so a PUT can be retried safely.
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

export function newUlid(now: number = Date.now()): string {
  let time = '';
  let t = now;
  for (let i = 0; i < 10; i++) {
    time = ALPHABET[t % 32] + time;
    t = Math.floor(t / 32);
  }
  const rand = crypto.getRandomValues(new Uint8Array(16));
  let tail = '';
  for (let i = 0; i < 16; i++) tail += ALPHABET[rand[i] % 32];
  return time + tail;
}

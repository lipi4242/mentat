const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
export function newId() {
  let t = Date.now(), prefix = '';
  for (let i = 0; i < 10; i++) { prefix = ALPHABET[t % 32] + prefix; t = Math.floor(t / 32); }
  return prefix + [...crypto.getRandomValues(new Uint8Array(16))].map(n => ALPHABET[n % 32]).join('');
}

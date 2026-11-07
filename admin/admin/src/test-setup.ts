// jsdom lacks matchMedia, which antd's responsive hooks call on mount, and
// React needs the act flag to run effects synchronously under test.
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

// Report desktop breakpoints so antd renders the sider inline rather than the
// collapsed mobile drawer — otherwise the nav (and its logout item) is absent
// from the DOM and any test touching it silently tests nothing.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes('min-width'),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

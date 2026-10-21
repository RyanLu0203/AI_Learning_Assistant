// A Basic Auth proxy reserves Authorization for its own login. Its UI response
// opts into a separate browser-to-proxy header; the backend still receives Bearer.
export function bearerHeaders(token, browserDocument = globalThis.document) {
    const meta = browserDocument?.querySelector?.('meta[name="aila-bearer-header"]');
    const header = meta?.content === "X-App-Authorization"
        ? "X-App-Authorization"
        : "Authorization";
    return { [header]: `Bearer ${token}` };
}

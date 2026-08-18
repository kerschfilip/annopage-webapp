async function apiFetch(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail || JSON.stringify(body);
        } catch (e) {
            // ignore
        }
        throw new Error(detail);
    }
    return res.json();
}

<script>
async function generatePKCE() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);

    const codeVerifier = btoa(String.fromCharCode(...array))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

    const encoder = new TextEncoder();
    const data = encoder.encode(codeVerifier);
    const digest = await crypto.subtle.digest("SHA-256", data);

    const codeChallenge = btoa(
        String.fromCharCode(...new Uint8Array(digest))
    ).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

    return { codeVerifier, codeChallenge };
}
</script>

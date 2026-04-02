export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  return {
    ok: response.ok,
    status: response.status,
    data: response.ok ? await response.json() : null,
    response,
  };
}

export async function fetchText(url, options = {}) {
  const response = await fetch(url, options);
  return {
    ok: response.ok,
    status: response.status,
    text: response.ok ? await response.text() : "",
    response,
  };
}

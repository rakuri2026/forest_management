/**
 * Download a file from an API endpoint using fetch with auth token.
 * Extracts filename from Content-Disposition header (backup: fallback name).
 * Supports RFC 5987 UTF-8 encoding for Unicode filenames (Nepali).
 */
export async function downloadFromApi(
  url: string,
  fallbackFilename: string,
  extraParams?: Record<string, string>,
  options?: { method?: string; body?: unknown }
): Promise<void> {
  const token = localStorage.getItem('access_token');
  const separator = url.includes('?') ? '&' : '?';
  const fullUrl = extraParams && (!options || options.method !== 'POST')
    ? url + separator + new URLSearchParams(extraParams).toString()
    : url;

  const fetchOptions: RequestInit = {
    method: options?.method || 'GET',
    headers: { Authorization: `Bearer ${token}` } as Record<string, string>,
  };

  if (options?.method === 'POST' && options.body !== undefined) {
    (fetchOptions.headers as Record<string, string>)['Content-Type'] = 'application/json';
    (fetchOptions as any).body = JSON.stringify(options.body);
  }

  const response = await fetch(fullUrl, fetchOptions);

  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail || body;
    } catch {}
    throw new Error(detail || `Export failed (${response.status})`);
  }

  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';

  const match =
    disposition.match(/filename\*?=UTF-8''([^;]+)/) ||
    disposition.match(/filename="([^"]+)"/);
  const filename = match ? decodeURIComponent(match[1]) : fallbackFilename;

  const urlObj = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = urlObj;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(urlObj);
}

/**
 * Download client-side generated content (blob) with a given filename.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers);

  // Do not set Content-Type for FormData, the browser does it with the correct boundary.
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle token expiration gracefully
  if (response.status === 401) {
    try {
      const errorData = await response.clone().json(); // Clone to read body safely
      if (errorData.message && errorData.message.includes('expired')) {
        console.error('Session expired. Redirecting to login.');
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('english_name');
        // Redirect to login page with a message
        window.location.href = `/admin/login?message=${encodeURIComponent('Session expired, please log in again.')}`;
        // Return a promise that will not resolve to prevent further processing
        return new Promise<Response>(() => {});
      }
    } catch (e) {
      // The 401 response was not JSON, handle as a generic error
      console.error('Received a non-JSON 401 error.', e);
    }
  }

  return response;
};

import type { APIRoute } from 'astro';

export const prerender = false;

const MAILERLITE_ENDPOINT = 'https://connect.mailerlite.com/api/subscribers';

const isValidEmail = (value: string) => /.+@.+\..+/.test(value);

export const POST: APIRoute = async ({ request, url }) => {
  const apiKey = import.meta.env.MAILERLITE_API_KEY;
  const defaultGroup = import.meta.env.MAILERLITE_GROUP_ID;

  if (!apiKey) {
    return new Response(
      JSON.stringify({ message: 'Newsletter not configured. Add MAILERLITE_API_KEY.' }),
      { status: 500 }
    );
  }

  const contentType = request.headers.get('content-type') || '';
  let email = '';
  let botcheck = '';
  let redirect = '';

  if (contentType.includes('application/json')) {
    const payload = await request.json().catch(() => ({}));
    email = (payload.email || '').trim();
    botcheck = (payload.botcheck || '').trim();
    redirect = (payload.redirect || '').trim();
  } else {
    const formData = await request.formData();
    email = String(formData.get('email') || '').trim();
    botcheck = String(formData.get('botcheck') || '').trim();
    redirect = String(formData.get('redirect') || '').trim();
  }

  if (botcheck) {
    return new Response(JSON.stringify({ message: 'Spam detected.' }), { status: 400 });
  }

  if (!email || !isValidEmail(email)) {
    return new Response(JSON.stringify({ message: 'A valid email is required.' }), { status: 400 });
  }

  const payload: Record<string, unknown> = {
    email,
    ...(defaultGroup ? { groups: [defaultGroup] } : {}),
  };

  const response = await fetch(MAILERLITE_ENDPOINT, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const message = error?.message || 'Unable to save subscriber right now.';
    return new Response(JSON.stringify({ message }), { status: 502 });
  }

  const acceptsHtml = (request.headers.get('accept') || '').includes('text/html');
  const isNavigate = request.headers.get('sec-fetch-mode') === 'navigate';
  if (acceptsHtml || isNavigate) {
    return new Response(null, {
      status: 303,
      headers: { Location: redirect || '/?subscribed=1' },
    });
  }

  return new Response(JSON.stringify({ message: 'Subscription saved.' }), { status: 201 });
};

export const GET: APIRoute = async () =>
  new Response(null, {
    status: 303,
    headers: { Location: '/?subscribed=1' },
  });

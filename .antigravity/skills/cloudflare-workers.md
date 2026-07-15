# 3.8 Cloudflare Workers Skill
Edge computing ด้วย JS/TS พร้อม KV Storage

### Code Pattern
```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === '/api/cache') {
      const key = url.searchParams.get('key');
      const cached = await env.MY_KV.get(key);
      if (cached) return Response.json({ data: JSON.parse(cached), source: 'cache' });
    }
    return new Response('Not Found', { status: 404 });
  }
};
```
# 6.3 Cloud Deployment Skills (Vercel, AWS, GCP)
Vercel config & Cloud native deployment headers

### Code Pattern
```json
{
  "framework": "nextjs",
  "headers": [{ "source": "/(.*)", "headers": [{ "key": "X-Frame-Options", "value": "DENY" }] }]
}
```
# 3.3 Node.js Backend Patterns
รวบรวม patterns สำหรับสร้าง Node.js APIs (Express.js/Fastify) พร้อม Error Handling

### Code Pattern
```javascript
const express = require('express');
const router = express.Router();

const asyncHandler = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

router.get('/users/:id', asyncHandler(async (req, res) => {
  const user = await UserService.findById(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  return res.json({ data: user });
}));
```
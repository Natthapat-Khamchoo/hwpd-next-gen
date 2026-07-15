# 7.2 MongoDB & NoSQL Patterns
Aggregation pipeline patterns

### Code Pattern
```javascript
db.orders.aggregate([
  { $match: { status: 'completed' } },
  { $group: { _id: { year: { $year: '$createdAt' } }, total: { $sum: '$total' } } }
]);
```
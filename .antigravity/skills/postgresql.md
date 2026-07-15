# 7.1 PostgreSQL Skill
Indexing (Partial, Covering, GIN) และ Keyset Pagination

### Code Pattern
```sql
CREATE INDEX idx_metadata_gin ON items USING GIN(metadata);
SELECT * FROM items WHERE metadata @> '{"category": "electronics"}';
```
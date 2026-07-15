# 4.4 TypeScript & JavaScript Pack
Advanced TS patterns, Utility types

### Code Pattern
```typescript
type ApiResponse<T> =
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }
  | { status: 'loading' };
```
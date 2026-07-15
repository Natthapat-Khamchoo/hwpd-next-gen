# 4.1 React Patterns Skill
Modern React patterns, Custom Hooks และ Performance optimization

### Code Pattern
```typescript
import { useState, useEffect, useCallback } from 'react';

function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const fetchData = useCallback(async () => {
    const res = await fetch(url);
    setData(await res.json());
  }, [url]);
  useEffect(() => { fetchData(); }, [fetchData]);
  return { data, refetch: fetchData };
}
```
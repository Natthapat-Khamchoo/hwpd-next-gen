# 3.5 NestJS Framework with Drizzle ORM
NestJS ร่วมกับ Drizzle ORM สำหรับ Type-safe database access

### Code Pattern
```typescript
import { drizzle } from 'drizzle-orm/node-postgres';
import { pgTable, serial, text } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  email: text('email').notNull().unique()
});

@Injectable()
export class UsersService {
  constructor(@InjectDrizzle() private db: NodePgDatabase) {}
  async findAll() { return await this.db.select().from(users); }
}
```
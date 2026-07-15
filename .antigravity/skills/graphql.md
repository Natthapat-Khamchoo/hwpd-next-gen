# 8.2 GraphQL Architect Skill
Schema design, Mutations payload pattern และ Error handling

### Code Pattern
```graphql
type Mutation {
  createUser(input: CreateUserInput!): UserPayload!
}
type UserPayload {
  user: User
  errors: [UserError!]!
}
```
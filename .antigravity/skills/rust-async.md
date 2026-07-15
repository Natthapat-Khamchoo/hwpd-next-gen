# 3.7 Rust Async Patterns
ครอบคลุม async/await patterns ด้วย Tokio และ Axum

### Code Pattern
```rust
use axum::{Router, routing::get, Json, extract::Path};
use tokio::net::TcpListener;

#[tokio::main]
async fn main() {
    let app = Router::new().route("/users/:id", get(get_user));
    let listener = TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
```
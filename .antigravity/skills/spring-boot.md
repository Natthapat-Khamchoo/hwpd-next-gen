# 3.4 Spring Boot Skills
ครอบคลุม Actuator, Cache, CRUD และ REST API Standards

### Code Pattern
```java
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {
    @GetMapping
    public ResponseEntity<Page<ProductDTO>> getProducts(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(productService.findAll(PageRequest.of(page, size)));
    }
}
```
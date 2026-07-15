# 3.1 AWS SDK for Java 2.x Skill
ครอบคลุม AWS SDK for Java 2.x ที่ใช้ใน Lambda functions, SQS, SNS และ S3

### Code Pattern
```java
public class OrderProcessor implements RequestHandler<SQSEvent, Void> {
    private final SqsClient sqsClient = SqsClient.builder().region(Region.AP_SOUTHEAST_1).build();
    @Override
    public Void handleRequest(SQSEvent event, Context context) {
        event.getRecords().forEach(record -> {
            processOrder(JSON.parseObject(record.getBody(), Order.class));
        });
        return null;
    }
}
```
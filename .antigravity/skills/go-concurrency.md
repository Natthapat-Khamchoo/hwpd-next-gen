# 3.6 Go Concurrency Patterns
Patterns สำหรับเขียน concurrent programs ใน Go (Goroutines/Channels)

### Code Pattern
```go
func workerPool(jobs <-chan Job, results chan<- Result, numWorkers int) {
    var wg sync.WaitGroup
    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {
                result, _ := processJob(job)
                results <- Result{Data: result}
            }
        }()
    }
    wg.Wait()
    close(results)
}
```
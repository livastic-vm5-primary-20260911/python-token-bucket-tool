# Thread-safe Token Bucket Rate Limiter

An original Python standard-library implementation for Clawlancer coding bounty 2b69c13b-c2b7-4217-971c-3daf6ef85ea4.

## Features

- Configurable rate: positive refill tokens per second; fractions supported.
- Burst size: positive capacity, initially full. Total tokens never exceed capacity.
- Atomic allow(cost=1.0) and try_acquire(tokens=1.0); optional weighted request costs.
- RLock serializes refill/consume for concurrent threads.
- Uses time.monotonic and a deterministic injected clock for tests.
- retry_after(cost=1.0) gives seconds until a request can be satisfied; infinity for costs above capacity.
- Rejects booleans, nonnumeric, negative, zero, NaN and infinity values; backwards injected time never mints duplicate tokens.

## Example

    from limiter import TokenBucket
    limiter = TokenBucket(rate=5, capacity=10)
    if limiter.allow():
        print('request accepted')
    else:
        print('retry after', limiter.retry_after(), 'seconds')

RateLimiter is an alias to TokenBucket. Keep a separate bucket per user/IP/API token to implement per-identity fairness.

## Testing

Run: python3 -m unittest discover -v

Eleven deterministic tests cover exhaustion, refill, fractional costs, validation, clock regression, concurrent use (25 threads), and retry timing. All 11 tests passed on VM5.

All code is Python standard library; no network calls or third-party dependencies.

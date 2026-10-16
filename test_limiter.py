"""Run with: python3 -m unittest discover -v"""
import math
import threading
import unittest

from limiter import TokenBucket, RateLimiter


class FakeClock:
    def __init__(self, initial=100.0):
        self.t = float(initial)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class TokenBucketTests(unittest.TestCase):
    def test_allows_burst_and_then_denies(self):
        c = FakeClock()
        b = TokenBucket(rate=2, capacity=3, clock=c)
        self.assertTrue(b.allow())
        self.assertTrue(b.allow())
        self.assertTrue(b.allow())
        self.assertFalse(b.allow())
        self.assertAlmostEqual(b.retry_after(), 0.5)

    def test_refill_after_elapsed_time(self):
        c = FakeClock()
        b = TokenBucket(rate=2, capacity=3, clock=c)
        for _ in range(3):
            self.assertTrue(b.allow())
        c.advance(0.5)
        self.assertAlmostEqual(b.available, 1.0)
        self.assertTrue(b.allow())
        self.assertFalse(b.allow())
        c.advance(2.0)
        self.assertAlmostEqual(b.available, 3.0)

    def test_burst_ceiling_not_exceeded(self):
        c = FakeClock()
        b = TokenBucket(10, 4, clock=c)
        c.advance(100_000)
        self.assertEqual(b.available, 4)
        self.assertEqual(sum(b.allow() for _ in range(5)), 4)

    def test_fractional_and_custom_cost(self):
        c = FakeClock()
        b = TokenBucket(rate=0.5, capacity=2.5, clock=c)
        self.assertTrue(b.allow(1.75))
        self.assertFalse(b.allow(1.0))
        self.assertAlmostEqual(b.retry_after(1.0), 0.5)
        c.advance(0.5)
        self.assertTrue(b.try_acquire(1.0))
        self.assertAlmostEqual(b.available, 0)

    def test_retry_after_exceeds_capacity(self):
        c = FakeClock()
        b = TokenBucket(4, 2, clock=c)
        self.assertTrue(math.isinf(b.retry_after(4)))
        self.assertFalse(b.allow(4))

    def test_no_consumption_on_denial(self):
        c = FakeClock()
        b = TokenBucket(1, 1, clock=c)
        self.assertFalse(b.allow(1.1))
        self.assertEqual(b.available, 1)

    def test_timestamp_backwards_not_double_credit(self):
        c = FakeClock()
        b = TokenBucket(rate=1, capacity=3, clock=c)
        self.assertTrue(b.allow(3))
        c.advance(1)
        self.assertEqual(b.available, 1)
        c.advance(-2)
        self.assertEqual(b.available, 1)
        c.advance(2)
        self.assertEqual(b.available, 1)
        c.advance(1)
        self.assertEqual(b.available, 2)

    def test_zero_negative_inf_nan_rejected(self):
        for bad in (0, -1, math.inf, -math.inf, math.nan):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    TokenBucket(rate=bad, capacity=1)
                with self.assertRaises(ValueError):
                    TokenBucket(rate=1, capacity=bad)
                with self.assertRaises(ValueError):
                    TokenBucket(rate=1, capacity=1).allow(bad)

    def test_bool_and_strings_rejected(self):
        for bad in (True, False, "3", None):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    TokenBucket(bad, 1)
                with self.assertRaises(TypeError):
                    TokenBucket(1, bad)
                with self.assertRaises(TypeError):
                    TokenBucket(1, 1).allow(bad)

    def test_alias_and_public_properties(self):
        self.assertIs(RateLimiter, TokenBucket)
        b = RateLimiter(rate=10, capacity=5)
        self.assertEqual(b.rate, 10)
        self.assertEqual(b.capacity, 5)
        self.assertTrue(b.try_acquire())

    def test_multithread_concurrent_consumption(self):
        c = FakeClock()
        b = TokenBucket(rate=1, capacity=200, clock=c)
        successes = []
        lock = threading.Lock()
        barrier = threading.Barrier(25)

        def worker():
            barrier.wait()
            count = sum(b.allow() for _ in range(20))
            with lock:
                successes.append(count)

        threads = [threading.Thread(target=worker) for _ in range(25)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=5)
        self.assertTrue(all(not th.is_alive() for th in threads))
        self.assertEqual(sum(successes), 200)
        self.assertEqual(b.available, 0)


if __name__ == "__main__":
    unittest.main()

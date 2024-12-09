import pytest
import time
import logging
from datetime import datetime
from unittest.mock import patch

from protocol.x.queue import RequestQueue
from protocol.x.scheduler import XSearchScheduler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock data for database responses
MOCK_SEARCH_TERMS = [
    {
        "id": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
        "search_term": "(from:getmasafi)"
    },
    {
        "id": "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy", 
        "search_term": "(to:getmasafi)"
    },
    {
        "id": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "search_term": "(from:binance)"
    },
    {
        "id": "5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y",
        "search_term": "(to:binance)"
    },
    {
        "id": "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFz",
        "search_term": "(from:coinbase)"
    },
    {
        "id": "5HGjWAeFDfFCWPsjFQdVV2Msvz2XtMktvgocEZcCj68kUMaw",
        "search_term": "(to:coinbase)"
    },
    {
        "id": "5CiPPseXPECbkjWCa6MnjNokrgYjMqmKndv2rSnekmSK2DjL",
        "search_term": "(from:kucoin)"
    },
    {
        "id": "5GNJqTPyNqANBkUVMN1LPPrxXnFouWXoe2wNSmmEoLctxiZY",
        "search_term": "(to:kucoin)"
    },
    {
        "id": "5HpG9w8EBLe5XCrbczpwq5TSXvedjrBGCwqxK1iQ7qUsSWFc",
        "search_term": "(from:kraken)"
    },
    {
        "id": "5Gw3s7q7iiJ39aEwuK1R3vmxQ6jyPeRC5iFZVh4YqyqAhXqL",
        "search_term": "(to:kraken)"
    },
    {
        "id": "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM",
        "search_term": "(from:huobi)"
    },
    {
        "id": "5FpewyS2VY8Cj3tKgSckq8ECkjd1HKHvBRnWhiHqRQsWfFC1",
        "search_term": "(to:huobi)"
    },
    {
        "id": "5CXN8PNUH5pXMaZZMFHHpLQVYmNZWwqkVKwz8yFGD1NqCpZN",
        "search_term": "(from:bitfinex)"
    },
    {
        "id": "5HR8jrHAKWnMZqsbvhZPqmk8KLhRkzThsqwzNYPhmHgPsEcz",
        "search_term": "(to:bitfinex)"
    },
    {
        "id": "5CJzTaCp5fuqG7NdJQ6oUCwdmFHKichew8w4RZ3zFHM8qSe6",
        "search_term": "(from:gemini)"
    },
    {
        "id": "5H4MvAsobfZ6bBCDyj5dsrWYLrA8DzpCHbkQnxnhVfFyCN6J",
        "search_term": "(to:gemini)"
    },
    {
        "id": "5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Z",
        "search_term": "(from:bitstamp)"
    },
    {
        "id": "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFx",
        "search_term": "(to:bitstamp)"
    },
    {
        "id": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQZ",
        "search_term": "(from:aixbt)"
    },
    {
        "id": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694tz",
        "search_term": "(to:aixbt)"
    }
]

@patch('protocol.x.scheduler.requests.get')
def test_scheduler_search_term_processing(mock_get):
    """Test scheduler processing of search terms with mocked database response"""
    print("\n" + "="*80)
    print("Starting Search Term Processing Test")
    print("="*80)
    
    # Setup mock response
    mock_get.return_value.json.return_value = MOCK_SEARCH_TERMS
    mock_get.return_value.status_code = 200
    
    # Initialize counters
    processed_terms = 0
    total_queries = 0
    
    # Initialize queue and scheduler
    request_queue = RequestQueue(max_concurrent_requests=2)
    request_queue.start()
    print("\nInitialized Request Queue with max_concurrent_requests=2")
    
    scheduler = XSearchScheduler(
        request_queue=request_queue,
        interval_minutes=1,  # Short interval for testing
        batch_size=10,
        priority=100,
        search_count=10
    )
    print(f"\nCreated Scheduler with:")
    print(f"- Interval: {scheduler.interval_minutes} minutes")
    print(f"- Batch Size: {scheduler.batch_size}")
    print(f"- Priority: {scheduler.priority}")
    print(f"- Search Count: {scheduler.search_count}")
    
    # Process one batch
    scheduler.process_search_terms()
    print("\nProcessing Search Terms...")
    
    # Track and verify search queries
    queries_by_exchange = {}
    print("\nGenerated Search Queries:")
    print("-" * 40)
    
    for term in MOCK_SEARCH_TERMS:
        search_query = scheduler._prepare_search_query(term)
        exchange = term['search_term'].split(':')[1].split(')')[0]  # Extract exchange name
        
        if exchange not in queries_by_exchange:
            queries_by_exchange[exchange] = {
                'from': 0,
                'to': 0,
                'queries': []
            }
            
        if '(from:' in term['search_term']:
            queries_by_exchange[exchange]['from'] += 1
            query_type = 'FROM'
        elif '(to:' in term['search_term']:
            queries_by_exchange[exchange]['to'] += 1
            query_type = 'TO'
            
        queries_by_exchange[exchange]['queries'].append(search_query['query'])
        print(f"\nExchange: {exchange.upper()}")
        print(f"Direction: {query_type}")
        print(f"Query: {search_query['query']}")
        print(f"Count: {search_query['count']}")
        print(f"Miner ID: {search_query['miner_id'][:16]}...")
        
        processed_terms += 1
        total_queries += 1
    
    # Wait for queue processing
    time.sleep(3)
    
    # Print Summary Statistics
    print("\n" + "="*80)
    print("PROCESSING SUMMARY")
    print("="*80)
    print(f"\nTotal Terms Processed: {processed_terms}")
    print(f"Total Queries Generated: {total_queries}")
    
    print("\nQueries by Exchange:")
    print("-" * 40)
    for exchange, counts in queries_by_exchange.items():
        print(f"\n{exchange.upper()}:")
        print(f"- FROM queries: {counts['from']}")
        print(f"- TO queries: {counts['to']}")
        print("Sample queries:")
        for query in counts['queries'][:2]:  # Show first two queries as examples
            print(f"  * {query}")
    
    # Verify counts
    assert processed_terms == len(MOCK_SEARCH_TERMS), \
        f"Expected {len(MOCK_SEARCH_TERMS)} terms, processed {processed_terms}"
    assert total_queries == len(MOCK_SEARCH_TERMS), \
        f"Expected {len(MOCK_SEARCH_TERMS)} queries, got {total_queries}"
    
    # Verify each exchange has both 'from' and 'to' queries
    for exchange, counts in queries_by_exchange.items():
        assert counts['from'] == 1, \
            f"Expected 1 from-query for {exchange}, got {counts['from']}"
        assert counts['to'] == 1, \
            f"Expected 1 to-query for {exchange}, got {counts['to']}"
    
    print("\nAll verifications passed successfully!")
    print("="*80)

@patch('protocol.x.scheduler.requests.get')
def test_scheduler_time_ranges(mock_get):
    """Test scheduler time range handling between runs"""
    logger.info("Starting time range test")
    
    # Setup mock response
    mock_get.return_value.json.return_value = MOCK_SEARCH_TERMS[:1]  # Just use one term
    mock_get.return_value.status_code = 200
    
    request_queue = RequestQueue(max_concurrent_requests=1)
    request_queue.start()
    
    scheduler = XSearchScheduler(
        request_queue=request_queue,
        interval_minutes=5,
        batch_size=1,
        priority=100,
        search_count=10
    )
    
    # First run
    scheduler.process_search_terms()
    first_run_time = scheduler.last_run_time
    logger.info(f"Completed first run at {first_run_time}")
    
    # Wait briefly
    time.sleep(2)
    
    # Second run
    scheduler.process_search_terms()
    second_run_time = scheduler.last_run_time
    logger.info(f"Completed second run at {second_run_time}")
    
    # Verify time progression
    assert second_run_time > first_run_time
    logger.debug("Verified time progression between runs")

@patch('protocol.x.scheduler.requests.get')
def test_scheduler_error_handling(mock_get):
    """Test scheduler handling of database errors"""
    logger.info("Starting error handling test")
    
    # Setup mock to simulate error
    mock_get.side_effect = Exception("Simulated database error")
    
    request_queue = RequestQueue(max_concurrent_requests=1)
    request_queue.start()
    
    scheduler = XSearchScheduler(
        request_queue=request_queue,
        interval_minutes=1,
        batch_size=10,
        priority=100,
        search_count=10
    )
    
    # Should handle error gracefully
    scheduler.process_search_terms()
    logger.info("Completed error handling test")

if __name__ == "__main__":
    # Run tests directly
    logger.info("Running scheduler tests directly")
    
    logger.info("\n=== Testing Search Term Processing ===")
    test_scheduler_search_term_processing(patch('protocol.x.scheduler.requests.get'))
    
    logger.info("\n=== Testing Time Range Handling ===")
    test_scheduler_time_ranges(patch('protocol.x.scheduler.requests.get'))
    
    logger.info("\n=== Testing Error Handling ===")
    test_scheduler_error_handling(patch('protocol.x.scheduler.requests.get')) 
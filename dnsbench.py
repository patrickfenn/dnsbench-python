import requests
import json
import dns.resolver
import dns.asyncresolver
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import multiprocessing
from multiprocessing import Manager
import ipaddress
import random

###############################################################################

NAMESERVER_URL = "https://raw.githubusercontent.com/trickest/resolvers/refs/heads/main/resolvers.txt"

DOMAIN_URL = "https://raw.githubusercontent.com/Kikobeats/top-sites/refs/heads/master/top-sites.json"

# Configure minimum success rate for a nameserver to be considered viable
# ie. if 8/10 queries return a NXDOMAIN or something it skips that nameserver
# Lowering it may result in nameservers that are on average quicker, but also
# increases the failure rate.
MIN_SUCCESS_PERCENTAGE = 0.9

# Output file that only contains ips of the nameservers
RANKING_RAW_OUTPUT_FILE = "nameserver_rankings_raw.txt"

# Output file that contains additional info of the nameservers
RANKING_STATS_OUTPUT_FILE = "nameserver_rankings_stats.txt"

# How many nameservers are output at the end (sorted by response time)
NUMBER_RANKINGS = 500

# How long each query will wait until it bails
RESOLVE_TIMEOUT = 0.5

# How many domains that will be used on each nameserver
# Note that the MIN_SUCCESS_PERCENTAGE may need to be tweaked
# if this is too high, or the list is low quality.
#MAX_DOMAINS = 100

# How many nameservers will be used out of the list downloaded
#MAX_NAMESERVERS = 1000

# How many processes the lookups will be distributed upon
NUM_PROCESSES = 4

# Filter nameserver in the same subnet that are slower than the quickest
FILTER_SUBNET = True

# Nameserver that is used to filter out domains that may not be valid at the start
BASELINE_NAMESERVER = "8.8.8.8" # Google nameserver

###############################################################################

# Supply your own nameserver file read in function
"""
def get_nameservers() -> [str]:
    ...
"""

# Supply your own domain file read in function
"""
def get_domains() -> [str]:
    ...
"""

def download_file(url):
    """Downloads a file from the given URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return ""

def is_valid_ip(ip_str):
    """Validate if a string is a valid IP address."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def parse_nameservers(content):
    """Parses a string content into a list of nameserver IPs."""
    if not content:
        return set()
    nameservers = set()
    for line in content.splitlines():
        line = line.strip()
        if line and is_valid_ip(line):
            nameservers.add(line)
    return [name for name in nameservers]

def parse_domains(content):
    """Parses JSON content and extracts rootDomain values."""
    if not content:
        return []
    try:
        data = json.loads(content)
        root_domains = [item["rootDomain"] for item in data if "rootDomain" in item]
        return root_domains
    except json.JSONDecodeError as e:
        print(f"Error parsing domain JSON: {e}")
        return []

async def resolve_domain_async(resolver, domain):
    """Resolves a single domain asynchronously and measures time taken."""
    start_time = time.time()
    try:
        await asyncio.wait_for(resolver.resolve(domain, 'A'), timeout=RESOLVE_TIMEOUT)
        end_time = time.time()
        return (end_time - start_time) * 1000  # Convert to milliseconds
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout,
            dns.exception.DNSException, asyncio.TimeoutError):
        return -1

async def benchmark_nameserver_async(ns_ip, test_domains):
    """Benchmarks a single nameserver using async DNS resolution."""
    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers = [ns_ip]
    resolver.timeout = RESOLVE_TIMEOUT
    resolver.lifetime = RESOLVE_TIMEOUT
    
    resol_times = []
    failed_count = 0
    
    # Create all tasks
    tasks = [resolve_domain_async(resolver, domain) for domain in test_domains]

    # Process results as they complete
    for coro in asyncio.as_completed(tasks):
        result = await coro
        resol_times.append(result)
        
        if result == -1:
            failed_count += 1
            
        # Early stopping if too many failures
        if failed_count > len(test_domains) * (1 - MIN_SUCCESS_PERCENTAGE):
            # Cancel remaining tasks
            for task in tasks:
                if isinstance(task, asyncio.Task) and not task.done():
                    task.cancel()
            # Mark remaining as failed
            resol_times.extend([-1] * (len(test_domains) - len(resol_times)))
            break
    
    valid_times = [t for t in resol_times if t != -1]
    successful_resolutions = len(valid_times)
    total_domains_tested = len(test_domains)
    
    success_rate = successful_resolutions / total_domains_tested if total_domains_tested > 0 else 0
    
    if success_rate < MIN_SUCCESS_PERCENTAGE or successful_resolutions == 0:
        average_time = -1
    else:
        average_time = sum(valid_times) / successful_resolutions
    
    return ns_ip, average_time, successful_resolutions, total_domains_tested

def benchmark_nameserver(ns_ip, test_domains):
    """Synchronous wrapper for async benchmark."""
    return asyncio.run(benchmark_nameserver_async(ns_ip, test_domains))

def benchmark_nameserver_batch(nameserver_batch, test_domains, progress_queue):
    """Benchmarks a batch of nameservers."""
    results = []
    
    for ns_ip in nameserver_batch:
        result = benchmark_nameserver(ns_ip, test_domains)
        results.append(result)
        progress_queue.put(1)
    
    return results

def validate_domains(test_domains):
    valid_domains = []
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [BASELINE_NAMESERVER]
    for i in range(len(test_domains)):
        try:
            resolver.resolve(test_domains[i], 'A')
            valid_domains.append(test_domains[i])
            progress = float(i / len(test_domains))
            print(f"\rProgress: {progress:6.2%}", end="", flush=True)
        except:
            pass
    print()
    return valid_domains

def main():
    print("--- Starting DNS Bench ---")

    # 1. Obtain nameserver list
    if 'get_nameservers' in globals():
        nameserver_ips = get_nameservers()
    else:
        print(f"Downloading nameservers from: {NAMESERVER_URL}")
        nameserver_content = download_file(NAMESERVER_URL)
        nameserver_ips = parse_nameservers(nameserver_content)
        if not nameserver_ips:
            print("No nameservers found or downloaded. Exiting.")
            return
        print(f"Found {len(nameserver_ips)} nameservers.")
        if 'MAX_NAMESERVERS' in globals():
            if FILTER_SUBNET is True:
                # It's possible for there to many nameserver in the same subnet right after another
                # which would end up getting filtered at the end.
                random.shuffle(nameserver_ips)
            nameserver_ips = nameserver_ips[:MAX_NAMESERVERS]
    print(f"Using {len(nameserver_ips)} nameservers for testing.\n")

    # 2. Obtain domains
    if 'get_domains' in globals():
        test_domains = get_domans()
    else:
        print(f"Downloading domains from: {DOMAIN_URL}")
        domain_content = download_file(DOMAIN_URL)
        root_domains = parse_domains(domain_content)
        if not root_domains:
            print("No domains found or downloaded. Exiting.")
            return
        print(f"Found {len(root_domains)} domains.")
        if 'MAX_DOMAINS' in globals():
            test_domains = root_domains[:MAX_DOMAINS]
        else:
            test_domains = root_domains
        print("--- Validating domains using baseline nameserver ---")
        test_domains = validate_domains(test_domains)
    print(f"Using {len(test_domains)} domains for testing.\n")

    # 3. Split nameservers into batches for multiprocessing
    batch_size = max(1, len(nameserver_ips) // NUM_PROCESSES)
    nameserver_batches = [
        nameserver_ips[i:i + batch_size] 
        for i in range(0, len(nameserver_ips), batch_size)
    ]

    # 4. Run the benchmark
    print(f"--- Benchmarking Nameservers using {NUM_PROCESSES} processes ---")
    nameserver_rankings_list = []
    total_nameservers = len(nameserver_ips)
    completed_nameservers = 0

    # Create a manager and queue for progress tracking
    with Manager() as manager:
        progress_queue = manager.Queue()
        
        # Use ProcessPoolExecutor for parallel processing
        with ProcessPoolExecutor(max_workers=NUM_PROCESSES) as process_executor:
            futures = {
                process_executor.submit(benchmark_nameserver_batch, batch, test_domains, progress_queue): batch 
                for batch in nameserver_batches
            }
            
            # Monitor progress queue
            all_done = False
            while not all_done:
                while not progress_queue.empty():
                    progress_queue.get()
                    completed_nameservers += 1
                    progress = float(completed_nameservers / total_nameservers)
                    print(f"\rProgress: {progress:6.2%}", end="", flush=True)
                
                all_done = all(future.done() for future in futures)
                
                if not all_done:
                    time.sleep(0.05)
            
            # Collect results
            for future in as_completed(futures):
                batch_results = future.result()
                for ns_ip, average_time, successful_resolutions, total_domains in batch_results:
                    if average_time != -1:
                        nameserver_rankings_list.append((ns_ip, average_time))
            print()
    if len(nameserver_rankings_list) == 0:
        print("No nameservers found, issue with resolving.")
        print("Possible issue with domain count and MIN_SUCCESS_PERCENTAGE")
        return
    print(f"Nameservers benchmarked: {len(nameserver_rankings_list)}\n")

    # 5. Rank nameservers by how quickly they responded
    sorted_rankings = sorted(nameserver_rankings_list, key=lambda item: item[1])

    if FILTER_SUBNET:
        print("Filtering nameservers by subnet...")
        filtered_rankings = []
        seen_networks = set()

        # 6. Filter out nameservers that are slower than others in their subnet
        for ns_ip, avg_time in sorted_rankings:
            if avg_time == -1:
                continue  # Skip nameservers that failed to resolve

            try:
                ip_obj = ipaddress.ip_address(ns_ip)
                if isinstance(ip_obj, ipaddress.IPv4Address):
                    # Use /24 for IPv4 subnets
                    network = ipaddress.ip_network(f"{ns_ip}/24", strict=False)
                elif isinstance(ip_obj, ipaddress.IPv6Address):
                    # Use /64 for IPv6 subnets
                    network = ipaddress.ip_network(f"{ns_ip}/64", strict=False)
                else:
                    continue # Should not happen

                if network not in seen_networks:
                    seen_networks.add(network)
                    filtered_rankings.append((ns_ip, avg_time))
            except ipaddress.AddressValueError:
                # Handle cases where ns_ip might not be a valid IP address
                print(f"Warning: Invalid IP address encountered: {ns_ip}")
                continue
        print(f"Filtered down to {len(filtered_rankings)} unique subnet nameservers.\n")
    else:
        print("Skipping subnet filtering.\n")

    # 7. Dump
    stats_file = open(RANKING_STATS_OUTPUT_FILE, "w")
    raw_file = open(RANKING_RAW_OUTPUT_FILE, "w")
    for rank, (ns_ip, avg_time) in enumerate(filtered_rankings[:NUMBER_RANKINGS]):
        stats_file.write(f"{rank+1}. Nameserver: {ns_ip} - Average Resolution Time: {avg_time:.2f} ms\n")
        raw_file.write(f"{ns_ip}\n")

    stats_file.close()
    raw_file.close()

    print(f"Completed! Results saved to {RANKING_RAW_OUTPUT_FILE} and {RANKING_STATS_OUTPUT_FILE}")

if __name__ == "__main__":
    main()

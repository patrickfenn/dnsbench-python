# dnsbench-python
A simple dns benchmark python3 script

# Features:
- Queries each nameserver with a customizable amount of domains.
- Multiproccessed, so a large amount of nameservers can be tested quickly.
- Filters out any nameserver that is not the quickest in a subnet.

# Credits
- Full credit to trickest/resolvers repo for the nameserver list
- Full credit to Kikobeats/top-sites repo for the domain list

# How to run:

Clone this repo then change to it's directory. Then run the following commands:

```
python3 -m venv venv # create a venv
source venv/bin/activate # activate it
pip install -r requirements.txt # install the reqs
python3 dnsbench.py
```

The script will then create 2 files, one with a new line delimited nameservers, another with the same nameservers but what their average response time was to the queries. The former is especially helpful for programs such as adguardhome or pihole that accept custom forwarders.

# Output example

nameserver_rankings_raw.txt
```
172.64.37.250
23.216.52.159
172.64.47.224
172.64.36.249
162.159.36.141
223.5.5.187
173.223.99.124
172.64.46.50
88.221.162.94
45.90.28.161
```

nameserver_rankings_stats.txt
```
1. Nameserver: 172.64.37.250 - Average Resolution Time: 42.50 ms
2. Nameserver: 23.216.52.159 - Average Resolution Time: 42.98 ms
3. Nameserver: 172.64.47.224 - Average Resolution Time: 43.30 ms
4. Nameserver: 172.64.36.249 - Average Resolution Time: 43.78 ms
5. Nameserver: 162.159.36.141 - Average Resolution Time: 45.28 ms
6. Nameserver: 223.5.5.187 - Average Resolution Time: 47.20 ms
7. Nameserver: 173.223.99.124 - Average Resolution Time: 48.35 ms
8. Nameserver: 172.64.46.50 - Average Resolution Time: 49.37 ms
9. Nameserver: 88.221.162.94 - Average Resolution Time: 49.48 ms
10. Nameserver: 45.90.28.161 - Average Resolution Time: 49.70 ms
```
# dnsbench-python
A simple dns benchmark python3 script

# Features:
- Queries each nameserver with a customizable amount of domains.
- Multiproccessed, so a large amount of nameservers can be tested quickly.
- Filters out any nameserver that is not the quickest in a subnet.

Full credit to trickest/resolvers repo for the nameserver list
Full credit to Kikobeats/top-sites repo for the domain list

# How to run:

Clone this repo then change to it's directory. Then run the following commands:

```
python3 -m venv venv # create a venv
source venv/bin/activate # activate it
pip install -r requirements.txt # install the reqs
python3 dnsbench.py
```

The script will then create 2 files, one with a new line delimited nameservers, another with the same nameservers but what their average response time was to the queries. The former is especially helpful for programs such as adguardhome or pihole that accept custom forwarders.
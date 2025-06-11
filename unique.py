file = open("AutoScout24_ZIP.csv","r")
unique = set()
for line in file:
    line=line.strip().split(",")
    url = line[-1]
    unique.add(url)

print(len(unique))

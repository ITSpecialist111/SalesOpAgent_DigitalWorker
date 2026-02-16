def find_line(filename, queries):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            for query in queries:
                if query.lower() in line.lower():
                    print(f"Match '{query}' at line {i+1}")
                    # Print 2 lines before and 5 lines after
                    start = max(0, i - 2)
                    end = min(len(lines), i + 6)
                    for j in range(start, end):
                        print(f"{j+1}: {lines[j].strip()}")
                    print("-" * 20)

if __name__ == "__main__":
    queries = ["Extend agents", "Agent 365 SDK", "Agent 365 development"]
    find_line("pdf_content.txt", queries)

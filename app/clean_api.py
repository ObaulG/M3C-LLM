with open('api_server.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i < 30:
            print(repr(line))

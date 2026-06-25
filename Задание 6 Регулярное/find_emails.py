import re

with open('dev.txt', 'r', encoding='utf-8') as f:
    text = f.read()

emails = re.findall(
    r'\b[A-Za-z0-9._%+-]+@hotmail\.[A-Za-z]{2,}\b',
    text
)

with open("FoundedEmails.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(emails))
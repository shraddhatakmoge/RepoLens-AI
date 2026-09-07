from src.rag.chain import ask_repository


question = "What does this repository contain?"

answer = ask_repository(question)

print("\nANSWER:\n")
print(answer)
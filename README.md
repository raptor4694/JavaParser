# JavaParser
### Description
This is a complete Java parser written in Python. It parses Java code into 
trees as defined in `java/tree.py`, where every possible code construct is represented by its own class. For ease of use, instead of each tree just containing a list of subtrees, it actually has named members defining its unique parts. Each tree's `__str__` method is written to produce its representation as valid Java code. Theoretically, this program's input should match its output (minus non-doc comments).
### Usage
`java.py [-h] [--type {Java}] [--out FILE] FILE`
### Why this exists
I am aware that other implementations of Java parsers in Python exist. I made this to use as a base for other projects I want to make which will extend the vanilla Java syntax, and as such it has some extra features which may be lacking in other implementations of Java parsers.
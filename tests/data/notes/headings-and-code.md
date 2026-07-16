# Heading One

## Heading Two

Headings above are not tags, but this is: #markdown

```python
# This comment is not a tag
value = "#neither-is-this"
```

Inline `#not-a-tag` is skipped as well, though #markdown still counts here.

~~~
# A tilde-fenced comment, also skipped
~~~

Documenting Markdown itself needs a longer outer fence. The inner ``` must not
close the outer ````, or the example below would spill back into the prose:

````markdown
```
#not-a-tag-either
```
````

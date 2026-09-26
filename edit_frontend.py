import sys
with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

content = content.replace('const [text, setText] = useState("");', '''const [text, setText] = useState("");
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tpl = params.get("template");
    if (tpl) {
      setText(tpl);
    }
  }, []);
''')
with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

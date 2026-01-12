"""
Custom GraphiQL interface with example queries.

Serves a custom GraphiQL HTML page with a dropdown menu of example queries.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json

from ..graphql_examples import EXAMPLE_QUERIES, DEFAULT_QUERY

router = APIRouter()


def create_graphiql_html(graphql_endpoint: str = "/graphql") -> str:
    """
    Create custom GraphiQL HTML with example queries dropdown.

    Attributes:

        graphql_endpoint: The GraphQL endpoint URL

    Returns: HTML string for the GraphiQL interface
    """
    # Convert example queries to JavaScript format
    examples_js = json.dumps(EXAMPLE_QUERIES, indent=2)

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Medical Literature Knowledge Graph - GraphiQL</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='0.9em' font-size='80'>🧬</text></svg>">
    <style>
        body {{
            margin: 0;
            padding: 0;
            height: 100vh;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        #graphiql {{
            height: 100vh;
        }}
        .graphiql-container {{
            height: 100%;
        }}
        #examples-dropdown {{
            position: absolute;
            top: 10px;
            right: 60px;
            z-index: 100;
        }}
        #examples-dropdown select {{
            padding: 8px 12px;
            border: 1px solid #d6d6d6;
            border-radius: 4px;
            background: white;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        #examples-dropdown select:hover {{
            border-color: #b0b0b0;
        }}
        #examples-dropdown select:focus {{
            outline: none;
            border-color: #0070f3;
            box-shadow: 0 0 0 3px rgba(0,112,243,0.1);
        }}
    </style>
    <link rel="stylesheet" href="https://unpkg.com/graphiql@3/graphiql.min.css" />
</head>
<body>
    <div id="graphiql">Loading...</div>
    <div id="examples-dropdown">
        <select id="example-selector">
            <option value="">-- Select Example Query --</option>
        </select>
    </div>

    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/graphiql@3/graphiql.min.js"></script>

    <script>
        const examples = {examples_js};
        const {{ useState }} = React;

        // GraphQL fetcher function
        const fetcher = GraphiQL.createFetcher({{
            url: '{graphql_endpoint}',
        }});

        // GraphiQL component with state management
        function GraphiQLWithExamples() {{
            const [query, setQuery] = useState(`{DEFAULT_QUERY.replace("`", "`")}`);

            // Expose setQuery to window for dropdown access
            React.useEffect(() => {{
                window.setGraphiQLQuery = setQuery;
            }}, []);

            return React.createElement(GraphiQL, {{
                fetcher: fetcher,
                query: query,
                onEditQuery: setQuery
            }});
        }}

        // Render GraphiQL
        const root = ReactDOM.createRoot(document.getElementById('graphiql'));
        root.render(React.createElement(GraphiQLWithExamples));

        // Populate examples dropdown
        const selector = document.getElementById('example-selector');
        Object.keys(examples).forEach(name => {{
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            selector.appendChild(option);
        }});

        // Handle example selection
        selector.addEventListener('change', (e) => {{
            const selectedName = e.target.value;
            if (selectedName && examples[selectedName]) {{
                // Update the query in GraphiQL using the exposed setter
                if (window.setGraphiQLQuery) {{
                    window.setGraphiQLQuery(examples[selectedName]);
                }}
                // Reset dropdown to prompt
                setTimeout(() => {{
                    e.target.value = '';
                }}, 100);
            }}
        }});
    </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def graphiql_interface():
    """
    Serve custom GraphiQL interface with example queries dropdown.
    """
    return create_graphiql_html()

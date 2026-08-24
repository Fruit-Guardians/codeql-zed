/**
 * A small query used to exercise CodeQL syntax and language-server diagnostics.
 * @name CodeQL Zed fixture
 * @description A minimal valid query for local development.
 * @id codeql-zed/fixture
 */
from int value
where value = 1
select value, "CodeQL Zed fixture"

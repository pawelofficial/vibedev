"""
Column-level lineage parser for SQL DDL (CREATE TABLE / CREATE VIEW).

This is a pragmatic parser tailored to PostgreSQL-style DDL as found in
schema.txt. It handles:
- Direct passthrough columns
- Aliases and renamed columns
- Casts (::TYPE)
- CASE expressions
- COALESCE, NULLIF, LOWER, TRIM, UPPER, DATE_TRUNC, concatenation
- Arithmetic expressions
- Joins across multiple tables
- CTEs (WITH ... AS) - resolved transparently to real models
- Aggregate functions and filtered aggregates (COUNT, SUM, MIN, MAX, AVG + FILTER)
- UNION ALL
- Window functions (OVER (...))
- Views depending on other views
- SELECT * expansion
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional


@dataclass
class ColumnLineage:
    """Represents a single output column and its upstream sources."""
    model: str  # The model (table/view) this column belongs to
    column: str  # The output column name
    upstream: List[Tuple[str, str]]  # List of (model, column) upstream sources
    expression: str = ""  # The original SQL expression
    is_derived: bool = False  # True if derived from multiple columns or functions


@dataclass
class Model:
    """Represents a SQL table or view."""
    name: str
    model_type: str  # 'table' or 'view'
    columns: List[str] = field(default_factory=list)
    column_lineage: Dict[str, ColumnLineage] = field(default_factory=dict)


def parse_schema(sql_text: str) -> Dict[str, Model]:
    """Parse the full SQL schema text and return a dict of model_name -> Model."""
    models: Dict[str, Model] = {}

    # Extract CREATE TABLE statements
    table_pattern = re.compile(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);',
        re.DOTALL | re.IGNORECASE
    )
    for match in table_pattern.finditer(sql_text):
        table_name = match.group(1).lower()
        body = match.group(2)
        columns = _parse_table_columns(body)
        model = Model(name=table_name, model_type='table', columns=columns)
        # Base table columns have no upstream lineage
        for col in columns:
            model.column_lineage[col] = ColumnLineage(
                model=table_name, column=col, upstream=[], expression=col
            )
        models[table_name] = model

    # Extract CREATE VIEW statements (order matters - views can depend on earlier views)
    view_pattern = re.compile(
        r'CREATE\s+VIEW\s+(\w+)\s+AS\s+(.*?);(?=\s*(?:--|CREATE|DROP|$))',
        re.DOTALL | re.IGNORECASE
    )
    for match in view_pattern.finditer(sql_text):
        view_name = match.group(1).lower()
        view_sql = match.group(2).strip()
        model = _parse_view(view_name, view_sql, models)
        models[view_name] = model

    return models


def _parse_table_columns(body: str) -> List[str]:
    """Extract column names from a CREATE TABLE body."""
    columns = []
    for line in body.split('\n'):
        line = line.strip().rstrip(',')
        if not line:
            continue
        # Skip constraints
        if re.match(r'^\s*(PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT|REFERENCES)', line, re.IGNORECASE):
            continue
        # Extract column name (first word)
        col_match = re.match(r'(\w+)\s+', line)
        if col_match:
            col_name = col_match.group(1).lower()
            # Skip SQL keywords that might appear
            if col_name.upper() not in ('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT', 'INDEX'):
                columns.append(col_name)
    return columns


def _parse_view(view_name: str, view_sql: str, models: Dict[str, Model]) -> Model:
    """Parse a CREATE VIEW statement and extract column lineage.
    CTEs are resolved transparently - the final view's lineage references
    only real tables/views, not internal CTEs."""
    # Parse CTEs
    ctes, main_query = _parse_ctes(view_sql)

    # Build CTE models (internal, for resolution only)
    cte_models: Dict[str, Model] = {}
    all_available = dict(models)

    for cte_name, cte_sql in ctes:
        cte_model = _parse_subquery_as_model(cte_name, cte_sql, all_available, cte_models)
        cte_models[cte_name] = cte_model
        all_available[cte_name] = cte_model

    # Parse the main SELECT with CTEs available
    available_models = dict(all_available)
    model = _parse_select_as_model(view_name, main_query, available_models)
    model.model_type = 'view'

    # Resolve CTE references through to real models
    _resolve_cte_references(model, cte_models, models)

    return model


def _resolve_cte_references(model: Model, cte_models: Dict[str, Model], real_models: Dict[str, Model]):
    """Replace CTE upstream references with their own upstream sources (transitively).
    After this, the model's lineage only references real tables/views."""
    real_model_names = set(real_models.keys())

    # Build a mapping of CTE -> source tables (for fallback when a CTE column has no upstream)
    cte_source_tables: Dict[str, Set[str]] = {}
    for cte_name, cte_model in cte_models.items():
        sources = set()
        for col, lin in cte_model.column_lineage.items():
            for m, c in lin.upstream:
                if m in real_model_names:
                    sources.add(m)
                elif m in cte_models:
                    # Recursively get sources from nested CTE
                    for inner_col, inner_lin in cte_models[m].column_lineage.items():
                        for im, ic in inner_lin.upstream:
                            if im in real_model_names:
                                sources.add(im)
        cte_source_tables[cte_name] = sources

    for col_name, lineage in model.column_lineage.items():
        resolved = _resolve_upstream_through_ctes(
            lineage.upstream, cte_models, real_model_names, cte_source_tables, set()
        )
        lineage.upstream = resolved
        lineage.is_derived = len(resolved) > 1


def _resolve_upstream_through_ctes(
    upstream: List[Tuple[str, str]],
    cte_models: Dict[str, Model],
    real_model_names: Set[str],
    cte_source_tables: Dict[str, Set[str]],
    visited: Set[Tuple[str, str]]
) -> List[Tuple[str, str]]:
    """Recursively resolve CTE references to real model references."""
    result = []
    for model_name, col_name in upstream:
        key = (model_name, col_name)
        if key in visited:
            continue
        visited.add(key)

        if model_name in real_model_names:
            # Already a real model - keep it
            result.append((model_name, col_name))
        elif model_name in cte_models:
            # It's a CTE - resolve through to the CTE's own upstream
            cte = cte_models[model_name]
            if col_name in cte.column_lineage:
                cte_upstream = cte.column_lineage[col_name].upstream
                if cte_upstream:
                    resolved = _resolve_upstream_through_ctes(
                        cte_upstream, cte_models, real_model_names, cte_source_tables, visited
                    )
                    result.extend(resolved)
                else:
                    # CTE column has no column-level upstream (e.g., COUNT(*))
                    # Fall back to CTE's source tables - aggregates depend on source rows
                    if model_name in cte_source_tables:
                        for src_table in cte_source_tables[model_name]:
                            fallback_col = _get_fallback_column(cte, src_table, real_model_names)
                            if fallback_col:
                                result.append((src_table, fallback_col))
            else:
                # Column not found in CTE - try source tables as fallback
                if model_name in cte_source_tables:
                    for src_table in cte_source_tables[model_name]:
                        fallback_col = _get_fallback_column(cte, src_table, real_model_names)
                        if fallback_col:
                            result.append((src_table, fallback_col))
        else:
            # Unknown model - drop (it's likely a CTE that wasn't tracked)
            pass

    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for item in result:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _get_fallback_column(cte: Model, source_table: str, real_model_names: Set[str]) -> Optional[str]:
    """Find a fallback column for a CTE-to-table link.
    Uses columns that the CTE resolves to the given source table."""
    # Find any column in the CTE that traces to this source table
    for col, lin in cte.column_lineage.items():
        for m, c in lin.upstream:
            if m == source_table:
                return c
    # If nothing found, just use the first column from any link to that table
    return None


def _parse_ctes(sql: str) -> Tuple[List[Tuple[str, str]], str]:
    """Extract CTEs from a WITH ... SELECT statement.
    Returns list of (cte_name, cte_body_sql) and the main SELECT."""
    sql = sql.strip()
    if not re.match(r'WITH\s', sql, re.IGNORECASE):
        return [], sql

    # Remove leading WITH
    sql_after_with = sql[4:].strip()

    ctes = []
    remaining = sql_after_with

    while True:
        # Match CTE name and AS (
        cte_header = re.match(r'(\w+)\s+AS\s*\(', remaining, re.IGNORECASE)
        if not cte_header:
            break

        cte_name = cte_header.group(1).lower()
        # Find matching closing paren
        body_start = cte_header.end()
        paren_depth = 1
        pos = body_start
        while pos < len(remaining) and paren_depth > 0:
            if remaining[pos] == '(':
                paren_depth += 1
            elif remaining[pos] == ')':
                paren_depth -= 1
            pos += 1

        cte_body = remaining[body_start:pos - 1].strip()
        ctes.append((cte_name, cte_body))

        # Skip past the closing paren and any comma/whitespace
        remaining = remaining[pos:].strip()
        if remaining.startswith(','):
            remaining = remaining[1:].strip()
        # If we hit SELECT, that's the main query
        if re.match(r'SELECT\s', remaining, re.IGNORECASE):
            break

    return ctes, remaining


def _parse_subquery_as_model(
    name: str, sql: str, models: Dict[str, Model], cte_models: Dict[str, Model]
) -> Model:
    """Parse a subquery (CTE body) as if it were a model. Handles UNION ALL."""
    available = dict(models)
    available.update(cte_models)

    # Check for UNION ALL
    if _has_union_all(sql):
        return _parse_union_all_as_model(name, sql, available)

    # Check for nested CTEs
    nested_ctes, main_query = _parse_ctes(sql)
    if nested_ctes:
        for cte_name, cte_sql in nested_ctes:
            cte_model = _parse_subquery_as_model(cte_name, cte_sql, available, {})
            available[cte_name] = cte_model

    return _parse_select_as_model(name, main_query if nested_ctes else sql, available)


def _has_union_all(sql: str) -> bool:
    """Check if SQL contains UNION ALL at the top level (not inside parens)."""
    depth = 0
    upper = sql.upper()
    for i, ch in enumerate(sql):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and upper[i:i+9] == 'UNION ALL':
            return True
    return False


def _parse_union_all_as_model(name: str, sql: str, models: Dict[str, Model]) -> Model:
    """Parse a UNION ALL query. Columns come from all branches."""
    # Split at top-level UNION ALL
    parts = _split_union_all(sql)
    model = Model(name=name, model_type='view')

    # Parse each branch
    branch_models = []
    for part in parts:
        branch = _parse_select_as_model(f"{name}__branch", part.strip(), models)
        branch_models.append(branch)

    if not branch_models:
        return model

    # Use first branch for column names, merge lineage from all branches
    first = branch_models[0]
    model.columns = list(first.columns)
    for i, col in enumerate(model.columns):
        upstream = []
        for branch in branch_models:
            # Match by position if column names differ between branches
            if i < len(branch.columns):
                branch_col = branch.columns[i]
                if branch_col in branch.column_lineage:
                    upstream.extend(branch.column_lineage[branch_col].upstream)
            elif col in branch.column_lineage:
                upstream.extend(branch.column_lineage[col].upstream)
        # De-duplicate
        seen = set()
        deduped = []
        for item in upstream:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        expr = first.column_lineage.get(col, ColumnLineage(name, col, [])).expression
        model.column_lineage[col] = ColumnLineage(
            model=name, column=col, upstream=deduped,
            expression=expr, is_derived=len(deduped) > 1
        )

    return model


def _split_union_all(sql: str) -> List[str]:
    """Split SQL at top-level UNION ALL."""
    parts = []
    depth = 0
    upper = sql.upper()
    current_start = 0

    i = 0
    while i < len(sql):
        if sql[i] == '(':
            depth += 1
        elif sql[i] == ')':
            depth -= 1
        elif depth == 0 and upper[i:i+9] == 'UNION ALL':
            parts.append(sql[current_start:i].strip())
            i += 9
            current_start = i
            continue
        i += 1

    parts.append(sql[current_start:].strip())
    return parts


def _parse_select_as_model(name: str, sql: str, models: Dict[str, Model]) -> Model:
    """Parse a SELECT statement and build a Model with column lineage."""
    model = Model(name=name, model_type='view')

    # Extract FROM clause to determine table aliases
    aliases = _extract_from_aliases(sql, models)

    # Extract SELECT columns
    select_exprs = _extract_select_expressions(sql)

    for expr_text, alias in select_exprs:
        # Handle SELECT *
        if expr_text.strip() == '*':
            _expand_star(model, aliases, models)
            continue

        col_name = alias.lower() if alias else _infer_column_name(expr_text)
        if not col_name:
            continue
        model.columns.append(col_name)

        # Resolve upstream references
        upstream = _resolve_expression_sources(expr_text, aliases, models)
        model.column_lineage[col_name] = ColumnLineage(
            model=name, column=col_name, upstream=upstream,
            expression=expr_text.strip(),
            is_derived=len(upstream) > 1
        )

    return model


def _expand_star(model: Model, aliases: Dict[str, str], models: Dict[str, Model]):
    """Expand SELECT * by pulling columns from all source models."""
    for alias, model_name in aliases.items():
        if model_name in models:
            source_model = models[model_name]
            for col in source_model.columns:
                if col not in model.columns:
                    model.columns.append(col)
                    # Lineage: this column comes from the source model
                    source_lineage = source_model.column_lineage.get(col)
                    if source_lineage and source_lineage.upstream:
                        model.column_lineage[col] = ColumnLineage(
                            model=model.name, column=col,
                            upstream=list(source_lineage.upstream),
                            expression=col,
                            is_derived=source_lineage.is_derived
                        )
                    else:
                        model.column_lineage[col] = ColumnLineage(
                            model=model.name, column=col,
                            upstream=[(model_name, col)],
                            expression=col,
                            is_derived=False
                        )


def _extract_from_aliases(sql: str, models: Dict[str, Model]) -> Dict[str, str]:
    """Extract table/view aliases from FROM and JOIN clauses.
    Returns dict of alias -> model_name."""
    aliases = {}

    # Find FROM position at correct nesting level
    from_pos = _find_keyword_position(sql, 'FROM')
    if from_pos == -1:
        return aliases

    # Work on the portion from FROM onwards
    from_section = sql[from_pos:]

    # Extract table references with aliases from FROM and JOIN
    # Pattern: FROM/JOIN table_name [AS] alias
    table_ref_pattern = re.compile(
        r'(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?',
        re.IGNORECASE
    )

    sql_keywords_set = {
        'ON', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT',
        'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS', 'FULL',
        'JOIN', 'NATURAL', 'USING', 'SELECT', 'FROM', 'SET',
        'UNION', 'INTERSECT', 'EXCEPT', 'AND', 'OR', 'NOT',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS',
        'BY', 'ASC', 'DESC', 'NULLS', 'FIRST', 'LAST',
        'FILTER', 'OVER', 'PARTITION', 'WINDOW', 'WITH',
    }

    for match in table_ref_pattern.finditer(from_section):
        table_name = match.group(1).lower()
        alias = match.group(2)

        if alias and alias.upper() not in sql_keywords_set:
            aliases[alias.lower()] = table_name
        else:
            # No alias or alias is a keyword - use table name as its own alias
            aliases[table_name] = table_name

    return aliases


def _find_keyword_position(sql: str, keyword: str) -> int:
    """Find position of a SQL keyword at the top level (not inside parens)."""
    upper = sql.upper()
    kw = keyword.upper()
    kw_len = len(kw)
    depth = 0
    for i, ch in enumerate(sql):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and upper[i:i+kw_len] == kw:
            # Check word boundary
            before_ok = (i == 0 or not upper[i-1].isalnum() and upper[i-1] != '_')
            after_ok = (i + kw_len >= len(upper) or not upper[i+kw_len].isalnum() and upper[i+kw_len] != '_')
            if before_ok and after_ok:
                return i
    return -1


def _extract_select_expressions(sql: str) -> List[Tuple[str, Optional[str]]]:
    """Extract individual SELECT expressions and their aliases.
    Returns list of (expression_text, alias_or_None)."""
    # Find SELECT ... FROM boundary
    select_pos = _find_keyword_position(sql, 'SELECT')
    if select_pos == -1:
        return []

    from_pos = _find_keyword_position(sql, 'FROM')
    if from_pos == -1:
        return []

    select_body = sql[select_pos + 6:from_pos].strip()

    # Remove leading DISTINCT if present
    if select_body.upper().startswith('DISTINCT'):
        select_body = select_body[8:].strip()

    # Split by top-level commas
    expressions = _split_top_level_commas(select_body)

    result = []
    for expr in expressions:
        expr = expr.strip()
        if not expr:
            continue
        # Handle SELECT *
        if expr == '*':
            result.append(('*', None))
            continue

        # Extract alias: ... AS alias or just trailing identifier
        expr_text, alias = _extract_alias(expr)
        result.append((expr_text, alias))

    return result


def _split_top_level_commas(text: str) -> List[str]:
    """Split text by commas at the top level (not inside parens or quotes)."""
    parts = []
    depth = 0
    current = []
    in_single_quote = False

    for ch in text:
        if ch == "'" and not in_single_quote:
            in_single_quote = True
            current.append(ch)
        elif ch == "'" and in_single_quote:
            in_single_quote = False
            current.append(ch)
        elif in_single_quote:
            current.append(ch)
        elif ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)

    if current:
        parts.append(''.join(current))

    return parts


def _extract_alias(expr: str) -> Tuple[str, Optional[str]]:
    """Extract the alias from an expression. Returns (expression, alias)."""
    expr = expr.strip()

    # Handle ... AS alias (case insensitive, not inside parens)
    # Find the last top-level AS
    as_pos = _find_last_top_level_as(expr)
    if as_pos != -1:
        before = expr[:as_pos].strip()
        after = expr[as_pos + 2:].strip()
        alias = after.strip()
        return before, alias

    # No AS keyword - check if there's a simple trailing identifier
    return expr, None


def _find_last_top_level_as(expr: str) -> int:
    """Find the last occurrence of AS keyword at top level."""
    upper = expr.upper()
    depth = 0
    last_pos = -1
    in_single_quote = False

    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "'" and not in_single_quote:
            in_single_quote = True
        elif ch == "'" and in_single_quote:
            in_single_quote = False
        elif not in_single_quote:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0 and upper[i:i+2] == 'AS' and i + 2 < len(upper):
                # Check word boundaries
                before_ok = (i == 0 or not upper[i-1].isalnum() and upper[i-1] != '_')
                after_ok = not upper[i+2].isalnum() and upper[i+2] != '_'
                if before_ok and after_ok:
                    last_pos = i
        i += 1

    return last_pos


def _infer_column_name(expr: str) -> Optional[str]:
    """Infer column name from expression when no alias is given.
    E.g., 'table.column' -> 'column', 'column' -> 'column'."""
    expr = expr.strip()
    # Remove trailing ::TYPE cast
    expr = re.sub(r'::\w+(\([^)]*\))?$', '', expr).strip()

    # If it's a simple reference: table.column or just column
    match = re.match(r'^(?:\w+\.)?(\w+)$', expr)
    if match:
        return match.group(1).lower()

    return None


def _resolve_expression_sources(
    expr: str, aliases: Dict[str, str], models: Dict[str, Model]
) -> List[Tuple[str, str]]:
    """Resolve all column references in an expression to (model, column) tuples."""
    sources = set()

    # Remove string literals first
    clean_expr = re.sub(r"'[^']*'", '', expr)

    # Find qualified references: alias.column (exclude numeric decimals like 0.5)
    qualified_refs = re.findall(r'(\w+)\.(\w+)', clean_expr)
    for alias_name, col_name in qualified_refs:
        # Skip numeric literals (e.g., 0.5, 1.0)
        if alias_name.isdigit() or col_name.isdigit():
            continue
        alias_lower = alias_name.lower()
        col_lower = col_name.lower()
        if alias_lower in aliases:
            real_model = aliases[alias_lower]
            if real_model in models:
                # Verify column exists or accept it (CTE might have it)
                sources.add((real_model, col_lower))
            else:
                sources.add((real_model, col_lower))

    # ALSO try bare column resolution (always, not just when no qualified refs)
    # This handles columns from single-source CTEs/tables referenced without alias
    _resolve_bare_columns(clean_expr, aliases, models, sources)

    return sorted(sources)


def _resolve_bare_columns(
    clean_expr: str, aliases: Dict[str, str], models: Dict[str, Model],
    sources: Set[Tuple[str, str]]
):
    """Resolve unqualified (bare) column references in an expression."""
    sql_keywords = {
        'select', 'from', 'where', 'group', 'by', 'order', 'having', 'limit',
        'and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'as',
        'case', 'when', 'then', 'else', 'end', 'between', 'like', 'exists',
        'all', 'any', 'some', 'distinct', 'on', 'join', 'left', 'right',
        'inner', 'outer', 'cross', 'full', 'natural', 'using', 'union',
        'intersect', 'except', 'over', 'partition', 'rows', 'range',
        'filter', 'within', 'asc', 'desc', 'nulls', 'first', 'last',
        'with', 'recursive', 'boolean', 'text', 'integer', 'bigint',
        'numeric', 'date', 'timestamptz', 'timestamp',
    }
    sql_functions = {
        'count', 'sum', 'avg', 'min', 'max', 'coalesce', 'nullif',
        'lower', 'upper', 'trim', 'date_trunc', 'abs', 'cast',
        'dense_rank', 'rank', 'row_number', 'ntile', 'lag', 'lead',
        'current_date', 'current_timestamp', 'now', 'extract',
    }

    # Find bare identifiers not preceded by a dot
    # Use negative lookbehind for dot to avoid matching the second part of qualified refs
    bare_ids = re.findall(r'(?<!\.)(?<!\w)\b([a-zA-Z_]\w*)\b', clean_expr)
    for ident in bare_ids:
        ident_lower = ident.lower()
        if ident_lower in sql_keywords or ident_lower in sql_functions:
            continue
        # Skip if it looks like a type or numeric
        if ident.isdigit():
            continue
        # Skip if this is already captured via a qualified ref (check if preceded by a dot)
        # Try to find this column in available models referenced by aliases
        for alias_key, model_name in aliases.items():
            if model_name in models and ident_lower in models[model_name].columns:
                sources.add((model_name, ident_lower))
                break


def build_full_lineage(models: Dict[str, Model]) -> Dict[str, Dict[str, ColumnLineage]]:
    """Build complete lineage for all models.
    Returns dict: model_name -> {col_name -> ColumnLineage}."""
    return {name: model.column_lineage for name, model in models.items()}


def get_upstream_lineage(
    models: Dict[str, Model], model_name: str, column_name: str,
    visited: Optional[Set[Tuple[str, str]]] = None
) -> List[Tuple[str, str]]:
    """Recursively get all upstream sources for a given model.column."""
    if visited is None:
        visited = set()

    key = (model_name, column_name)
    if key in visited:
        return []
    visited.add(key)

    if model_name not in models:
        return [key]

    model = models[model_name]
    if column_name not in model.column_lineage:
        return [key]

    lineage = model.column_lineage[column_name]
    if not lineage.upstream:
        return [key]  # Base table column

    result = []
    for upstream_model, upstream_col in lineage.upstream:
        result.extend(get_upstream_lineage(models, upstream_model, upstream_col, visited))

    return result


def get_downstream_lineage(
    models: Dict[str, Model], model_name: str, column_name: str,
    visited: Optional[Set[Tuple[str, str]]] = None
) -> List[Tuple[str, str]]:
    """Get all downstream consumers of a given model.column."""
    if visited is None:
        visited = set()

    key = (model_name, column_name)
    if key in visited:
        return []
    visited.add(key)

    result = []
    for mname, model in models.items():
        for col, lin in model.column_lineage.items():
            if (model_name, column_name) in lin.upstream:
                result.append((mname, col))
                result.extend(get_downstream_lineage(models, mname, col, visited))

    return result


def get_lineage_graph(models: Dict[str, Model]) -> dict:
    """Build a JSON-serializable lineage graph for the frontend."""
    nodes = []
    edges = []

    for model_name, model in models.items():
        columns_data = []
        for col in model.columns:
            lin = model.column_lineage.get(col)
            columns_data.append({
                'name': col,
                'is_derived': lin.is_derived if lin else False,
                'expression': lin.expression if lin else col,
                'upstream_count': len(lin.upstream) if lin else 0,
            })
        nodes.append({
            'id': model_name,
            'type': model.model_type,
            'columns': columns_data,
        })

    # Build edges (column-to-column)
    for model_name, model in models.items():
        for col, lin in model.column_lineage.items():
            for upstream_model, upstream_col in lin.upstream:
                edges.append({
                    'source_model': upstream_model,
                    'source_column': upstream_col,
                    'target_model': model_name,
                    'target_column': col,
                })

    return {'nodes': nodes, 'edges': edges}

{% test expression_is_true(model, column_name=None, expression=None, arguments=None) %}
  {% if arguments is not none %}
    {% set expression = arguments.get('expression', expression) %}
  {% endif %}
  {% if expression is none %}
    {{ exceptions.raise_compiler_error('The `expression_is_true` test requires an `expression` argument.') }}
  {% endif %}

  select *
  from {{ model }}
  where not ({{ expression }}) or {{ expression }} is null
{% endtest %}

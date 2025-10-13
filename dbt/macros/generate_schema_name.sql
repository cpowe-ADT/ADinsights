{% macro generate_schema_name(custom_schema_name, node) %}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name -%}
        {%- set passthrough = ['raw', 'raw_google_ads', 'raw_meta'] -%}
        {%- if custom_schema_name in passthrough -%}
            {{ return(custom_schema_name) }}
        {%- else -%}
            {{ return(default_schema ~ '_' ~ custom_schema_name) }}
        {%- endif -%}
    {%- else -%}
        {{ return(default_schema) }}
    {%- endif -%}
{% endmacro %}

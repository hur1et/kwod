from .config import CONSTITUTION,constitution
from .store import encode
from .tools import definitions


def fresh_context(objective, files):
    memory = files.path('memory.md')
    strategy = files.path('strategy.md')
    text = ''
    if memory.exists():
        with memory.open('rb') as stream:
            text = stream.read(16384).decode('utf-8', errors='replace')
    strategy_text = ''
    if strategy.exists():
        with strategy.open('rb') as stream:
            strategy_text = stream.read(16384).decode('utf-8', errors='replace')
    return [{'role': 'user', 'content': objective},
            {'role': 'user', 'content': 'Workspace memory.md (at most 16384 bytes):\n' + text},
            {'role': 'user', 'content': 'Workspace strategy.md (at most 16384 bytes; agent-maintained strategic plan):\n' + strategy_text}]


def request(config, context):
    # Keep complete tool rounds and encrypted reasoning items for stateless continuation.
    # A hard boundary halts instead of silently dropping unresolved function calls.
    used = len(encode(context))
    if used > config.context_bytes:
        raise ValueError('context_limit')
    notice = (f'\nConversation input currently uses {used} of {config.context_bytes} bytes '
              '(a local byte limit, not a token count). Leave room for tool results. '
              'Use checkpoint before the limit to preserve your progress.')
    notice += ('\nExternal project identity is exclusively lowercase kwod. Never expand the project name in outgoing emails, subjects, signatures, offers or other public communication. '
        'Use observe_assets regularly, at orientation and before financial decisions. Its current observations include source timestamps and unknown/stale states; provider credits are not wallet cash. '
        'The infrastructure refreshes available balances every minute without model calls; failed reads are not evidence of insolvency. '
        'File tools use paths relative to your own workspace. Use list_files with path="." to list the workspace root. An empty path is accepted only by list_files. The /workspace/ prefix is an alias for that same workspace; it does not grant host-file access.')
    return {'model': config.model, 'instructions': constitution(config.mode, config.autonomy_level) + notice, 'input': context,
            'tools': definitions(config.autonomy_level), 'parallel_tool_calls': False, 'store': False,
            'include': ['reasoning.encrypted_content'], 'reasoning': {'effort': 'low'},
            'max_output_tokens': config.max_output_tokens, 'service_tier': 'default'}

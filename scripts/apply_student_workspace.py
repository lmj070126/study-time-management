"""Safely replace the long logged-in view in App.vue with StudentWorkspace.

Usage from repository root:
    python scripts/apply_student_workspace.py

The original App.vue is backed up before modifications. No backend or data files are touched.
"""
from pathlib import Path
import sys
import re


IMPORT_WORKSPACE = "import StudentWorkspace from './components/StudentWorkspace.vue'"
OBSOLETE_IMPORTS = [
    "import StudentTasks from './components/StudentTasks.vue'",
    "import StudentFocus from './components/StudentFocus.vue'",
    "import StudentAnalytics from './components/StudentAnalytics.vue'",
]
START = '    <div v-else class="dashboard">'
END = '    </div>\n  </div>\n</template>'
NEW_VIEW = (
    '    <StudentWorkspace v-else-if="user.role === \'student\'" :user="user" :token="accessToken" '
    '@logout="logout" @unauthorized="logout" />\n'
)


def apply(app_path: Path) -> str:
    if not app_path.is_file():
        raise ValueError(f'未找到前端文件: {app_path}')
    workspace_path = app_path.parent / 'components' / 'StudentWorkspace.vue'
    if not workspace_path.is_file():
        raise ValueError(f'请先将 StudentWorkspace.vue 复制到: {workspace_path}')
    for component in ('StudentTasks.vue', 'StudentFocus.vue', 'StudentAnalytics.vue'):
        if not (workspace_path.parent / component).is_file():
            raise ValueError(f'缺少原业务组件: {component}；请先合并 T1.6 并同步 main。')

    original = app_path.read_text(encoding='utf-8-sig')
    if '<StudentWorkspace v-else-if' in original:
        return '检测到 StudentWorkspace 已接入，无需重复修改。'
    start = original.find(START)
    if start < 0 or original.count(START) != 1:
        raise ValueError('未找到唯一的旧版 <div v-else class="dashboard">，已停止，未改动文件。')
    end = original.find(END, start)
    if end < 0 or original.find(END, end + 1) >= 0:
        raise ValueError('旧版 dashboard 结束位置不符合预期，已停止，未改动文件。')
    if '<StudentTasks' not in original[start:end] or '<StudentFocus' not in original[start:end]:
        raise ValueError('未识别出旧版任务、番茄钟组件，已停止，未改动文件。')
    # Preserve the original logged-in page for teacher/admin users. Only remove
    # student-specific modules from that fallback, then place the student shell
    # ahead of it as v-else-if.
    old_role_fallback = original[start:end + len('    </div>\n')]
    for component in ('StudentTasks', 'StudentFocus', 'StudentAnalytics'):
        if component == 'StudentAnalytics' and '<StudentAnalytics' not in old_role_fallback:
            continue  # T1.6 may have been added to the repo but not yet mounted in App.vue.
        pattern = rf'(?m)^      <{component}\b[\s\S]*?^      />\n'
        old_role_fallback, count = re.subn(pattern, '', old_role_fallback)
        if count != 1:
            raise ValueError(f'未找到唯一的 {component} 组件标签，已停止，未改动文件。')
    replaced = original[:start] + NEW_VIEW + old_role_fallback + original[end + len('    </div>\n'):]
    for old in OBSOLETE_IMPORTS:
        replaced = replaced.replace(old + '\n', '')
    if IMPORT_WORKSPACE not in replaced:
        anchor = "import axios from 'axios'\n"
        if anchor not in replaced:
            raise ValueError('缺少 App.vue 原有 axios import，已停止，未改动文件。')
        replaced = replaced.replace(anchor, anchor + IMPORT_WORKSPACE + '\n', 1)
    if replaced.count('<StudentWorkspace v-else-if') != 1 or '</template>' not in replaced:
        raise ValueError('生成结果未通过完整性检查，已停止，未改动文件。')

    backup = app_path.with_name('App.vue.before-t17.bak')
    if not backup.exists():
        backup.write_text(original, encoding='utf-8')
    app_path.write_text(replaced, encoding='utf-8')
    return f'修改成功：{app_path}\n原文件备份：{backup}'


def main() -> int:
    # Script lives under <repo>/scripts; discover root from its own location.
    root = Path(__file__).resolve().parents[1]
    try:
        print(apply(root / 'frontend' / 'src' / 'App.vue'))
        return 0
    except (ValueError, OSError) as err:
        print(f'操作停止：{err}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

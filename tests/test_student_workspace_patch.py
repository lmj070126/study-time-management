"""Offline tests for the non-destructive T1.7 App.vue migration script."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'apply_student_workspace.py'
spec = importlib.util.spec_from_file_location('workspace_apply', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

FIXTURE = '''<script setup>
import axios from 'axios'
import StudentTasks from './components/StudentTasks.vue'
import StudentFocus from './components/StudentFocus.vue'
import StudentAnalytics from './components/StudentAnalytics.vue'
const user = null
</script>
<template>
  <div class="page">
    <div v-if="!user" class="login-layout">login</div>
    <div v-else class="dashboard">
      <header class="dashboard-header">header</header>
      <StudentTasks
        v-if="user.role === 'student'"
        :token="accessToken"
        @unauthorized="logout"
      />
      <StudentFocus
        v-if="user.role === 'student'"
        :token="accessToken"
        @unauthorized="logout"
      />
      <StudentAnalytics
        v-if="user.role === 'student'"
        :token="accessToken"
        @unauthorized="logout"
      />
      <main class="dashboard-content">teacher/admin profile</main>
    </div>
  </div>
</template>
<style scoped>.page{min-height:100vh}</style>
'''

class TestMigration(unittest.TestCase):
    def setUp(self):
        self.context = TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        self.app = self.root / 'frontend' / 'src' / 'App.vue'
        self.app.parent.mkdir(parents=True)
        components = self.app.parent / 'components'
        components.mkdir()
        for name in ('StudentWorkspace.vue', 'StudentTasks.vue', 'StudentFocus.vue', 'StudentAnalytics.vue'):
            (components / name).write_text('<template/>', encoding='utf-8')
        self.app.write_text(FIXTURE, encoding='utf-8')

    def test_patch_preserves_role_fallback_and_login(self):
        mod.apply(self.app)
        patched = self.app.read_text(encoding='utf-8')
        self.assertIn('v-if="!user"', patched)
        self.assertIn('v-else-if="user.role === \'student\'"', patched)
        self.assertIn('<div v-else class="dashboard">', patched)
        self.assertIn('teacher/admin profile', patched)
        self.assertNotIn('<StudentTasks', patched)
        self.assertIn("import StudentWorkspace from './components/StudentWorkspace.vue'", patched)
        self.assertEqual((self.app.parent / 'App.vue.before-t17.bak').read_text(), FIXTURE)

    def test_works_with_main_without_analytics_mount(self):
        self.app.write_text(FIXTURE.replace("      <StudentAnalytics\n        v-if=\"user.role === 'student'\"\n        :token=\"accessToken\"\n        @unauthorized=\"logout\"\n      />\n", ''), encoding='utf-8')
        mod.apply(self.app)
        patched = self.app.read_text()
        self.assertIn('<StudentWorkspace v-else-if', patched)
        self.assertIn('teacher/admin profile', patched)

    def test_idempotent(self):
        mod.apply(self.app)
        snapshot = self.app.read_text()
        msg = mod.apply(self.app)
        self.assertIn('无需重复', msg)
        self.assertEqual(self.app.read_text(), snapshot)

    def test_unknown_layout_aborts_without_modifying(self):
        self.app.write_text('<template>custom</template>', encoding='utf-8')
        with self.assertRaises(ValueError):
            mod.apply(self.app)
        self.assertEqual(self.app.read_text(), '<template>custom</template>')
        self.assertFalse((self.app.parent / 'App.vue.before-t17.bak').exists())

if __name__ == '__main__':
    unittest.main()

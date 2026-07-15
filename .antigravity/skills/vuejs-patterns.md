# 4.2 Vue.js Patterns Skill
Vue 3 Composition API และ Pinia

### Code Pattern
```html
<script setup lang="ts">
import { ref, computed } from 'vue';
import { useUserStore } from '@/stores/user';
const userStore = useUserStore();
const searchQuery = ref('');
const filteredUsers = computed(() => userStore.users.filter(u => u.name.includes(searchQuery.value)));
</script>
```
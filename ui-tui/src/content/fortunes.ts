const FORTUNES = [
  '一次干净的重构，就能让代码豁然开朗',
  '一个小小的重命名，今天避免一个大 bug',
  '你的下一次 commit 信息将无懈可击',
  '你忽略的边缘情况，脑中已有答案',
  '最小改动，最大淡定',
  '今天适合大胆删除，而不是新增抽象',
  '正确的工具函数已经在你代码库里了',
  '在过度思考追上你之前，先发布',
  '测试即将拯救未来的你',
  '你的直觉——对那个分支的怀疑是对的'
]

const LEGENDARY = [
  '传奇掉落：一行修复，一次通过',
  '传奇掉落：所有不稳定测试一次性通过',
  '传奇掉落：你的 diff 本身就是一本教科书'
]

const hash = (s: string) => [...s].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0

const fromScore = (n: number) => {
  const rare = n % 20 === 0
  const bag = rare ? LEGENDARY : FORTUNES

  return `${rare ? '🌟' : '🔮'} ${bag[n % bag.length]}`
}

export const randomFortune = () => fromScore(Math.floor(Math.random() * 0x7fffffff))
export const dailyFortune = (seed: null | string) => fromScore(hash(`${seed || 'anon'}|${new Date().toDateString()}`))

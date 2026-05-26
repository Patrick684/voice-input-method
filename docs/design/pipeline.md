# 语音处理流水线

## 流水线概览

```
按住快捷键 → 录音采集 → 语音识别 → 标点恢复 → 语气修正 → Emoji注入 → 规则替换 → 文本输入
   ↓            ↓           ↓          ↓          ↓          ↓          ↓          ↓
HotkeyMgr   Recorder   Whisper    CT-Trans.  Punct.     Emoji     PostProc.   TextInjector
            (sd)       Engine     (FunASR)   Proc.      Inject.   (替换修正) (clipboard)
```

## 各阶段详解

### 1. 录音采集 (AudioRecorder)

- 采样率: 16000 Hz (Whisper 要求)
- 声道: 单声道
- 数据类型: float32
- 块大小: 50ms (800 samples)
- 触发: 按键按住开始，松开停止

音频数据以 numpy 数组形式收集在队列中，录音结束后拼接为完整数组。

### 2. 语音识别 (WhisperEngine)

输入: numpy float32 数组 (16kHz, mono)

处理步骤:
1. 音频格式校验 (长度 > 0.1秒)
2. 音频电平归一化
3. VAD 静音过滤 (跳过尾部静音)
4. 束搜索解码 (beam_size=5)
5. 热词 initial_prompt 注入
6. 清理残余标点，输出纯文本

输出: 无标点的纯文本

### 3. 标点恢复 (PunctuationRestorer - CT-Transformer)

输入: 无标点的纯文本

处理步骤:
1. CT-Transformer 神经网络语义分析
2. 基于上下文自动插入逗号、句号等标点
3. 加载失败时降级为规则方案（连接词+长句断句）
4. 短文本 (<3字) 跳过推理，直接加句号

输出: 带标点的文本

### 4. 语气修正 (PunctuationProcessor)

处理步骤:
1. 英文标点转中文标点 (中文语境检测)
2. 语气修正 (基于疑问词/感叹词/反问句式，将句号改为问号/感叹号)
3. 重复标点修正
4. 标点前后空格修正
5. (可选) 自动分段

### 5. Emoji 注入 (EmojiInjector)

处理步骤:
1. 按句子分割
2. 关键词匹配 emoji 规则
3. 按优先级选择最佳 emoji
4. 在句末标点前插入
5. 密度控制 (low/medium/high)

### 6. 规则替换 (PostProcessor)

处理步骤:
1. 依次应用所有启用的替换规则
2. 支持精确匹配替换（如"拍touch"→"PyTorch"）
3. 支持正则表达式替换
4. 预置规则覆盖 Whisper 常见中文识别错误

### 7. 文本输入 (TextInjector)

处理步骤:
1. 保存当前剪贴板内容
2. 将识别结果写入剪贴板
3. 模拟 Ctrl+V 粘贴
4. 等待粘贴完成
5. 恢复原始剪贴板

## 数据流类型

```
按键事件 (keyboard.Event)
    ↓
录音控制信号 (bool)
    ↓
音频数据 (np.ndarray, float32, shape=(N,))
    ↓
纯文本 (str, 无标点)
    ↓
标点恢复文本 (str, CT-Transformer)
    ↓
语气修正文本 (str)
    ↓
emoji 注入文本 (str)
    ↓
规则替换文本 (str)
    ↓
剪贴板操作 + 按键模拟
```

## 性能指标

| 阶段 | 耗时 (3秒语音) | 内存峰值 |
|------|---------------|----------|
| 录音采集 | 实时 | ~1 MB |
| 语音识别 | ~3 秒 | ~1.2 GB (medium) |
| 标点恢复 | ~0.5 秒 | ~300 MB (CT-Transformer) |
| 语气修正 | <1 ms | 可忽略 |
| Emoji 注入 | <1 ms | 可忽略 |
| 规则替换 | <1 ms | 可忽略 |
| 文本输入 | ~200 ms | 可忽略 |
| **总计** | **<4 秒** | **<1.8 GB** |

## 流式识别流水线

当启用流式识别时，流水线变为边说边识别模式：

```
按住快捷键 → 录音采集 → StreamVAD 切句 → 逐句识别 → 标点恢复 → 语气修正 → 逐句粘贴
   ↓            ↓            ↓               ↓          ↓          ↓          ↓
HotkeyMgr   Recorder    StreamVAD       Whisper    CT-Trans.  后处理链   clipboard
            (sd回调)    (Silero VAD)    Engine     (FunASR)             (每句即粘)
```

流式模式关键变化：
- **录音采集**: 通过 `on_audio_chunk` 回调实时将音频块送入 StreamVAD
- **StreamVAD 切句**: 基于 Silero VAD 神经网络检测语音活动段，语音概率连续低于阈值超过设定时间 (0.8s) 时判定句子结束；RMS 能量检测作为后备方案
- **底噪自适应**: 录音开始时前 0.5 秒采集环境噪音，自动校准 RMS 后备阈值
- **逐句识别**: 每个句子独立送入 Whisper 识别，识别结果经后处理后立即粘贴
- **剪贴板策略**: 录音开始时保存剪贴板，录音结束后统一恢复
- **尾句处理**: 松开按键时，将 StreamVAD 缓冲区剩余音频作为尾句处理

配置参数：
- `streaming_enabled`: 是否启用流式识别 (默认 False)
- `stream_silence_duration`: 静音切句时长，单位秒 (默认 0.8)
- `stream_silence_threshold`: RMS 后备静音阈值 (默认 0.015，自适应底噪时会覆盖)

## 文件转写流水线

音视频文件转写是独立于实时录音的另一个流水线，通过托盘菜单「转写文件...」触发：

```
选择文件 → pydub 提取音频 → Whisper 转写(带时间戳) → SRT/TXT 输出
   ↓            ↓                   ↓                      ↓
filedialog   AudioSegment      WhisperModel          保存字幕文件
             (ffmpeg)        (without_timestamps=F)   (filedialog)
```

支持的格式：
- 音频: mp3, wav, flac, m4a, ogg, wma, aac
- 视频: mp4, mkv, avi, mov, wmv, webm（通过 pydub/ffmpeg 提取音频）

输出格式：
- SRT: 带时间戳的标准字幕格式，可用于视频播放器
- TXT: 纯文本，每行一句

依赖：
- `pydub`: 音视频解码和音频重采样（16kHz mono float32）
- `ffmpeg`: 系统级依赖，pydub 需要它来处理非 wav 格式

## 错误处理

- 录音失败: 检查设备权限，显示通知
- 音频过短 (<0.1s): 静默丢弃
- 识别失败: 显示错误通知，恢复空闲状态
- 剪贴板失败: 显示通知，不覆盖原始内容

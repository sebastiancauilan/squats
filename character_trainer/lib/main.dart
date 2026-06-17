import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:image/image.dart' as img;
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:flutter_sound/flutter_sound.dart';

List<CameraDescription> cameras = [];
const String apiUrl = 'https://web-production-a5f3b.up.railway.app/predict';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(const CharacterTrainerApp());
}

class CharacterTrainerApp extends StatelessWidget {
  const CharacterTrainerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Character.Trainer',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(),
      home: const CameraScreen(),
    );
  }
}

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  
  DateTime _lastSent = DateTime.now();
  int _cleanStreak = 0;
bool _isPlayingVoice = false;
final FlutterSoundPlayer _soundPlayer = FlutterSoundPlayer();
static const String coachUrl = 'https://web-production-a5f3b.up.railway.app/coach-voice';
  late CameraController _controller;
  bool _isInitialized = false;
  bool _isSending = false;
  String _phase = '--';
  String _form = '';
  int _reps = 0;
  String _lastPhase = '';
  List<String> _phaseSequence = [];
  bool _isFront = true;
  String _mouthFrame = 'mouth_closed';
final Map<String, String> _voiceIds = {
  'tsundere': 'vGQNBgLaiM3EdZtxIiuY',
  'yandere': 'eVItLK1UvXctxuaRV2Oq',
  'dominant': 'cENJycK4Wg62xVikqkaA',
};
  String _personality = 'tsundere';
  final List<String> _personalities = ['tsundere', 'yandere', 'dominant'];


Future<List<int>> _convertCameraImage(CameraImage image) async {
  final bytes = image.planes[0].bytes;
  final width = image.width;
  final height = image.height;

  final rgbImage = img.Image(width: width, height: height);

  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      final int pixel = y * image.planes[0].bytesPerRow + x * 4;
      final int b = bytes[pixel];
      final int g = bytes[pixel + 1];
      final int r = bytes[pixel + 2];
      rgbImage.setPixelRgb(x, y, r, g, b);
    }
  }

  return img.encodeJpg(rgbImage);
} 
Future<void> _initSound() async {
  await _soundPlayer.openPlayer();
  await _soundPlayer.setSubscriptionDuration(const Duration(milliseconds: 80));
  _attachProgressListener();
}

void _attachProgressListener() {
  _soundPlayer.onProgress!.listen((e) {
    if (!_soundPlayer.isPlaying) return;
    setState(() {
      final ms = e.position.inMilliseconds % 240;
      if (ms < 80) _mouthFrame = 'mouth_closed';
      else if (ms < 160) _mouthFrame = 'mouth_half';
      else _mouthFrame = 'mouth_open';
    });
  });
}

Future<void> _playCoachAudio(String path) async {
  if (!_soundPlayer.isOpen()) {
    await _soundPlayer.openPlayer();
  }
  await _soundPlayer.startPlayer(
    fromURI: path,
    codec: Codec.mp3,
    whenFinished: () => setState(() => _mouthFrame = 'mouth_closed'),
  );
}
Future<void> _triggerCoachVoice({required String form, required int reps, required int streak}) async {
  if (_isPlayingVoice) return; // don't interrupt
  _isPlayingVoice = true;
  try {
  final response = await http.post(
    Uri.parse(coachUrl),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'form': form,
      'reps': reps,
      'streak': streak,
      'personality': _personality,
      'voice_id': _voiceIds[_personality] ?? 'vGQNBgLaiM3EdZtxIiuY',
    }),
  );

  // ADD THIS — log what you're actually getting back
  debugPrint('Coach status: ${response.statusCode}');
  debugPrint('Coach content-type: ${response.headers['content-type']}');
  debugPrint('Coach body length: ${response.bodyBytes.length}');

if (response.statusCode == 200 && 
    response.bodyBytes.length > 1000 &&
    response.headers['content-type']?.contains('audio') == true) {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/coach_voice.mp3');
    final sink = file.openWrite();
    sink.add(response.bodyBytes);
    await sink.flush();
    await sink.close();
    if (_soundPlayer.isPlaying) {
      await _soundPlayer.stopPlayer();
    }
    await _playCoachAudio(file.path);
  } else {
    debugPrint('Bad response: ${utf8.decode(response.bodyBytes)}');
  }
} catch (e) {
  debugPrint('Voice error: $e');
} finally {
  _isPlayingVoice = false; // move here so it always resets
}
}

  
Future<void> _toggleCamera() async {
  setState(() => _isInitialized = false);
  try { await _controller.stopImageStream(); } catch (_) {}
  _isFront = !_isFront;
  final selected = cameras.firstWhere(
    (c) => c.lensDirection == (_isFront ? CameraLensDirection.front : CameraLensDirection.back),
    orElse: () => cameras[0],
  );
  await _soundPlayer.closePlayer();
await _soundPlayer.openPlayer();
await _soundPlayer.setSubscriptionDuration(const Duration(milliseconds: 80));
_attachProgressListener();
  _controller = CameraController(selected, ResolutionPreset.medium, enableAudio: false);
  await _controller.initialize();
  await _controller.setFlashMode(FlashMode.off);
  if (mounted) {
    setState(() => _isInitialized = true);
    _startSending();
  }
}

  @override
void initState() {
  super.initState();
  _init();
}

Future<void> _init() async {
  await _initSound();
  await _initCamera();
}

  Future<void> _initCamera() async {
  if (cameras.isEmpty) return;
  _controller = CameraController(cameras[0], ResolutionPreset.medium, enableAudio: false);
    await _controller.initialize();
    await _controller.setFlashMode(FlashMode.off);
    if (mounted) {
      setState(() => _isInitialized = true);
      _startSending();
      
    }
  }

  void _startSending() {
  _controller.startImageStream((CameraImage image) async {
    if (_isSending || !mounted) return;
    if (DateTime.now().difference(_lastSent).inMilliseconds < 1000) return;
    _lastSent = DateTime.now();
    _isSending = true;
    try {
      final bytes = await _convertCameraImage(image);
      final request = http.MultipartRequest('POST', Uri.parse(apiUrl));
      request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'frame.jpg'));
      final response = await request.send();
      final body = await response.stream.bytesToString();
      final data = jsonDecode(body);

      final phase = data['phase'] ?? '--';
      final form = data['form'] ?? '';

      if (phase != _lastPhase) {
        _lastPhase = phase;
        if (phase == 'bottom') {
          _phaseSequence.add('bottom');
          if (form.isNotEmpty && form != 'Correct') {
            _cleanStreak = 0;
            _triggerCoachVoice(form: form, reps: _reps, streak: 0);
          }
        } else if (phase == 'ascending' && _phaseSequence.contains('bottom')) {
          _reps++;
          _phaseSequence = [];
          _cleanStreak++;
if (_reps % 3 == 0 || _cleanStreak % 3 == 0) {
  _triggerCoachVoice(form: 'Correct', reps: _reps, streak: _cleanStreak);
}
        }
      }

      if (mounted) setState(() { _phase = phase; _form = form; });
    } catch (e, stack) {
      debugPrint('Error: $e');
      debugPrint('Stack: $stack');
    }
    _isSending = false;
  });
}

  @override
void dispose() {
  _controller.dispose();
  _soundPlayer.closePlayer();
  super.dispose();
}

@override
Widget build(BuildContext context) {
  if (!_isInitialized) {
    return const Scaffold(
      backgroundColor: Colors.black,
      body: Center(child: CircularProgressIndicator()),
    );
  }

  return Scaffold(
    backgroundColor: Colors.black,
    body: Stack(
      fit: StackFit.expand,
      children: [
        CameraPreview(_controller),
        Positioned(
          top: 60, left: 20,
          child: Text('Phase: $_phase',
            style: const TextStyle(color: Colors.green, fontSize: 24, fontWeight: FontWeight.bold)),
        ),
        Positioned(
          top: 100, left: 20,
          child: Text('Reps: $_reps',
            style: const TextStyle(color: Colors.yellow, fontSize: 24, fontWeight: FontWeight.bold)),
        ),
        if (_form.isNotEmpty)
          Positioned(
            top: 140, left: 20,
            child: Text('Form: $_form',
              style: TextStyle(
                color: _form == 'Correct' ? Colors.green : Colors.red,
                fontSize: 24, fontWeight: FontWeight.bold)),
          ),
        Positioned(
          top: 60, right: 20,
          child: IconButton(
            icon: const Icon(Icons.flip_camera_ios, color: Colors.white, size: 32),
            onPressed: _toggleCamera,
          ),
        ),
        Positioned(
  top: 100, right: 20,
  child: DropdownButton<String>(
    value: _personality,
    dropdownColor: Colors.black87,
    style: const TextStyle(color: Colors.white, fontSize: 14),
    underline: const SizedBox(),
    menuMaxHeight: 150,
    items: _personalities.map((p) => DropdownMenuItem(
      value: p,
      child: Text(p),
    )).toList(),
    onChanged: (val) => setState(() => _personality = val!),
  ),
),
Positioned(
  bottom: 0,
  right: 0,
  child: Container(
  width: 180,
  height: 315,
    decoration: BoxDecoration(
      color: Colors.white.withOpacity(0.9),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Stack(
      children: [
        Positioned.fill(child: Image.asset('assets/characters/base/torso_female5.png', fit: BoxFit.fill)),
        Positioned.fill(child: Image.asset('assets/characters/face_shape/face.png', fit: BoxFit.fill)),
        Positioned.fill(child: Image.asset('assets/characters/mouth/$_mouthFrame.png', fit: BoxFit.fill)),
      ],
    ),
  ),
),
      ],
    ),
);
}
}
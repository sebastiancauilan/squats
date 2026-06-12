import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:just_audio/just_audio.dart';

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
  int _cleanStreak = 0;
bool _isPlayingVoice = false;
final AudioPlayer _audioPlayer = AudioPlayer();
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
        'personality': 'tsundere',
        'voice_id': 'YOUR_VOICE_ID_HERE',
      }),
    );
    if (response.statusCode == 200) {
      final bytes = response.bodyBytes;
      final source = LockCachingAudioSource(Uri.dataFromBytes(bytes, mimeType: 'audio/mpeg'));
      await _audioPlayer.setAudioSource(source);
      await _audioPlayer.play();
    }
  } catch (e) {
    debugPrint('Voice error: $e');
  }
  _isPlayingVoice = false;
}
Future<void> _toggleCamera() async {
  _isFront = !_isFront;
  final selected = cameras.firstWhere(
    (c) => c.lensDirection == (_isFront ? CameraLensDirection.front : CameraLensDirection.back),
    orElse: () => cameras[0],
  );
  await _controller.dispose();
  _controller = CameraController(selected, ResolutionPreset.medium, enableAudio: false);
  await _controller.initialize();
  await _controller.setFlashMode(FlashMode.off);
  if (mounted) setState(() {});
}

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    _controller = CameraController(cameras[0], ResolutionPreset.medium, enableAudio: false);
    await _controller.initialize();
    await _controller.setFlashMode(FlashMode.off);
    if (mounted) {
      setState(() => _isInitialized = true);
      _startSending();
    }
  }

  void _startSending() {
    Timer.periodic(const Duration(milliseconds: 500), (timer) async {
      if (!mounted) { timer.cancel(); return; }
      if (_isSending || !_controller.value.isInitialized) return;
      _isSending = true;
      debugPrint('Sending frame...');
      try {
        final image = await _controller.takePicture();
        final bytes = await image.readAsBytes();
        final request = http.MultipartRequest('POST', Uri.parse(apiUrl));
        request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: 'frame.jpg'));
        final response = await request.send();
        final body = await response.stream.bytesToString();
        final data = jsonDecode(body);

        final phase = data['phase'] ?? '--';
        debugPrint('Phase: $phase');
        final form = data['form'] ?? '';

if (phase != _lastPhase) {
  _lastPhase = phase;
  if (phase == 'bottom') {
    _phaseSequence.add('bottom');
    // Bad form — fire immediately
    if (form.isNotEmpty && form != 'Correct') {
      _cleanStreak = 0;
      _triggerCoachVoice(form: form, reps: _reps, streak: 0);
    }
  } else if (phase == 'ascending' && _phaseSequence.contains('bottom')) {
    _reps++;
    _phaseSequence = [];
    if (form == 'Correct' || form.isEmpty) {
      _cleanStreak++;
      // Encourage after 2 clean reps
      if (_cleanStreak % 2 == 0) {
        _triggerCoachVoice(form: 'Correct', reps: _reps, streak: _cleanStreak);
      }
    }
  }
}

        if (mounted) setState(() { _phase = phase; _form = form; });
      } catch (e) {
        debugPrint('Error: $e');
      }
      _isSending = false;
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
    _audioPlayer.dispose();
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
      ],
    ),
);
}
}
package pl.omulew.zegarsedziego

import android.media.AudioAttributes
import android.media.SoundPool
import android.os.Bundle
import android.os.SystemClock
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.*
import kotlinx.coroutines.delay
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent { ZegarSedziegoApp() }
    }
}

private enum class Phase { FIRST, FIRST_EXTRA, SECOND, SECOND_EXTRA }

private data class ClockState(
    val mainSec: Int = 0,
    val extraSec: Int = 0,
    val phase: Phase = Phase.FIRST,
    val running: Boolean = false
)

private class AudioEngine(context: android.content.Context) {
    private val pool = SoundPool.Builder()
        .setMaxStreams(3)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
        ).build()

    private val sounds = mapOf(
        "whistle" to pool.load(context, R.raw.whistle, 1),
        "15" to pool.load(context, R.raw.minute_15, 1),
        "30" to pool.load(context, R.raw.minute_30, 1),
        "60" to pool.load(context, R.raw.minute_60, 1),
        "75" to pool.load(context, R.raw.minute_75, 1),
    )
    fun play(key: String) { sounds[key]?.let { pool.play(it, 1f, 1f, 1, 0, 1f) } }
    fun doubleWhistle() {
        play("whistle")
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ play("whistle") }, 650)
    }
    fun release() = pool.release()
}

@Composable
private fun ZegarSedziegoApp() {
    var splash by rememberSaveable { mutableStateOf(true) }
    if (splash) {
        SplashScreen { splash = false }
    } else {
        MatchScreen()
    }
}

@Composable
private fun SplashScreen(onDone: () -> Unit) {
    val progress = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        progress.animateTo(1f, tween(2700))
        onDone()
    }
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        Image(
            painterResource(R.drawable.referee_splash),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop
        )
        Column(
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 28.dp).fillMaxWidth(.72f),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                Modifier.fillMaxWidth().height(8.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Color(0xCC152020))
            ) {
                Box(
                    Modifier.fillMaxWidth(progress.value).fillMaxHeight()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF45FF16))
                )
            }
            Spacer(Modifier.height(8.dp))
            Text("ŁADOWANIE…", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun MatchScreen() {
    val context = LocalContext.current
    val audio = remember { AudioEngine(context) }
    DisposableEffect(Unit) { onDispose { audio.release() } }

    var state by remember { mutableStateOf(ClockState()) }
    var baseTotal by remember { mutableLongStateOf(0L) }
    var startedAt by remember { mutableLongStateOf(0L) }
    val fired = remember { mutableStateListOf<Int>() }
    var showEditor by remember { mutableStateOf(false) }
    var showMenu by remember { mutableStateOf(false) }

    fun totalSecondsNow(): Long =
        if (!state.running) baseTotal
        else baseTotal + (SystemClock.elapsedRealtime() - startedAt) / 1000L

    fun derive(total: Long, running: Boolean = state.running): ClockState {
        val p = state.phase
        return when (p) {
            Phase.FIRST, Phase.FIRST_EXTRA -> {
                if (total >= 2700) ClockState(2700, (total - 2700).toInt(), Phase.FIRST_EXTRA, running)
                else ClockState(total.toInt(), 0, Phase.FIRST, running)
            }
            Phase.SECOND, Phase.SECOND_EXTRA -> {
                if (total >= 5400) ClockState(5400, (total - 5400).toInt(), Phase.SECOND_EXTRA, running)
                else ClockState(total.toInt(), 0, Phase.SECOND, running)
            }
        }
    }

    fun update() {
        val old = state.mainSec
        val n = derive(totalSecondsNow())
        state = n
        listOf(15,30,60,75).forEach { m ->
            if (old < m*60 && n.mainSec >= m*60 && !fired.contains(m)) {
                fired += m; audio.play(m.toString())
            }
        }
        val boundary = if (n.phase == Phase.FIRST_EXTRA) 2700 else if (n.phase == Phase.SECOND_EXTRA) 5400 else -1
        val key = if (boundary == 2700) 45 else if (boundary == 5400) 90 else -1
        if (key > 0 && old < boundary && !fired.contains(key)) {
            fired += key; audio.doubleWhistle()
        }
    }

    LaunchedEffect(state.running, startedAt, baseTotal, state.phase) {
        while (state.running) {
            update()
            delay(100)
        }
    }

    fun toggle() {
        if (state.running) {
            update()
            baseTotal = state.mainSec.toLong() + state.extraSec
            state = state.copy(running = false)
        } else {
            baseTotal = state.mainSec.toLong() + state.extraSec
            startedAt = SystemClock.elapsedRealtime()
            state = state.copy(running = true)
            audio.play("whistle")
        }
    }

    fun adjust(delta: Int) {
        if (state.running) update()
        val total = (state.mainSec.toLong() + state.extraSec + delta).coerceAtLeast(0)
        state = when {
            state.phase == Phase.FIRST_EXTRA ->
                ClockState(2700, (total-2700).coerceAtLeast(0).toInt(), Phase.FIRST_EXTRA, state.running)
            state.phase == Phase.SECOND_EXTRA ->
                ClockState(5400, (total-5400).coerceAtLeast(0).toInt(), Phase.SECOND_EXTRA, state.running)
            total < 2700 -> ClockState(total.toInt(),0,Phase.FIRST,state.running)
            else -> ClockState(total.coerceAtMost(5400).toInt(),0,Phase.SECOND,state.running)
        }
        baseTotal = state.mainSec.toLong()+state.extraSec
        if (state.running) startedAt = SystemClock.elapsedRealtime()
    }

    fun resetNext() {
        state = when (state.phase) {
            Phase.FIRST_EXTRA -> ClockState(2700,0,Phase.SECOND,false)
            Phase.SECOND_EXTRA -> ClockState(5400,0,Phase.SECOND,false)
            else -> ClockState()
        }
        baseTotal = state.mainSec.toLong()
        fired.clear()
    }

    val firstHalf = state.phase == Phase.FIRST || state.phase == Phase.FIRST_EXTRA
    val inExtra = state.phase == Phase.FIRST_EXTRA || state.phase == Phase.SECOND_EXTRA
    val accent = when {
        state.phase == Phase.SECOND_EXTRA -> Color(0xFFFF1520)
        state.phase == Phase.FIRST_EXTRA -> Color(0xFF18C8FF)
        firstHalf -> Color(0xFF7DFF22)
        else -> Color(0xFF18C8FF)
    }
    val progress = when (state.phase) {
        Phase.FIRST -> state.mainSec / 2700f
        Phase.SECOND -> (state.mainSec - 2700) / 2700f
        else -> 1f
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        Image(
            painterResource(R.drawable.stadium_bg), null,
            Modifier.fillMaxSize(), contentScale = ContentScale.Crop
        )
        Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha=.38f)))

        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(
                Modifier.fillMaxWidth().height(56.dp).padding(horizontal=18.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("☰", color=Color.White, fontWeight=FontWeight.Bold, fontSize=32.sp,
                    modifier=Modifier.clickable { showMenu=true }.padding(6.dp))
                Text(if(firstHalf) "I POŁOWA" else "II POŁOWA",
                    color=Color.White,fontWeight=FontWeight.Bold,fontSize=24.sp)
                Text("⚙", color=Color.White,fontWeight=FontWeight.Bold,fontSize=32.sp,
                    modifier=Modifier.clickable { showMenu=true }.padding(6.dp))
            }

            Box(Modifier.fillMaxWidth().weight(1f), contentAlignment=Alignment.Center) {
                Column(horizontalAlignment=Alignment.CenterHorizontally, modifier=Modifier.fillMaxWidth()) {
                    Box(Modifier.fillMaxWidth(.88f).aspectRatio(1f), contentAlignment=Alignment.Center) {
                        NeonDial(progress, accent)
                        Text(format(state.mainSec),color=Color.White,fontSize=64.sp,fontWeight=FontWeight.Black)
                if (inExtra) {
                    Box(Modifier.align(Alignment.BottomCenter).offset(y=24.dp)) {
                        AddedTimePanel(state.extraSec, accent)
                    }
                }
                    }

                    Spacer(Modifier.height(34.dp))
                    RoundStartButton(state.running, ::toggle)
                    Text(if(state.running) "PAUZA" else "START",color=Color.White,
                        fontWeight=FontWeight.Bold,fontSize=13.sp)
                    Spacer(Modifier.height(20.dp))

                    Row(Modifier.fillMaxWidth().padding(horizontal=28.dp), horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                        SmallButton("-1\nMIN",Modifier.weight(1f)){adjust(-60)}
                        SmallButton("-10\nS",Modifier.weight(1f)){adjust(-10)}
                        SmallButton("+10\nS",Modifier.weight(1f)){adjust(10)}
                        SmallButton("+1\nMIN",Modifier.weight(1f)){adjust(60)}
                    }
                    Spacer(Modifier.height(12.dp))
                    Row(Modifier.fillMaxWidth().padding(horizontal=40.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        SmallButton("EDYTUJ",Modifier.weight(1f)){showEditor=true}
                        SmallButton("RESET",Modifier.weight(1f)){resetNext()}
                    }
                }
            }

            HalfBar(firstHalf, accent)
        }
    }

    if(showMenu) {
        AlertDialog(
            onDismissRequest={showMenu=false},
            title={Text("ZEGAR SĘDZIEGO v8.0")},
            text={Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
                Button(onClick={audio.play("whistle")}){Text("TEST GWIZDKA")}
                Button(onClick={audio.play("15")}){Text("TEST GŁOSU – 15 MIN")}
            }},
            confirmButton={TextButton(onClick={showMenu=false}){Text("ZAMKNIJ")}}
        )
    }

    if(showEditor) {
        var edit by remember(state.mainSec) { mutableIntStateOf(state.mainSec) }
        AlertDialog(
            onDismissRequest={showEditor=false},
            title={Text("EDYCJA CZASU")},
            text={
                Column(horizontalAlignment=Alignment.CenterHorizontally) {
                    Text(format(edit),fontSize=44.sp,fontWeight=FontWeight.Black)
                    Row(horizontalArrangement=Arrangement.spacedBy(4.dp)) {
                        TextButton(onClick={edit=(edit-60).coerceAtLeast(0)}){Text("-1m")}
                        TextButton(onClick={edit=(edit-10).coerceAtLeast(0)}){Text("-10s")}
                        TextButton(onClick={edit=(edit+10).coerceAtMost(5999)}){Text("+10s")}
                        TextButton(onClick={edit=(edit+60).coerceAtMost(5999)}){Text("+1m")}
                    }
                }
            },
            confirmButton={
                TextButton(onClick={
                    state = if(edit<2700) ClockState(edit,0,Phase.FIRST,false)
                            else ClockState(edit.coerceAtMost(5400),0,Phase.SECOND,false)
                    baseTotal=state.mainSec.toLong(); fired.clear(); showEditor=false
                }){Text("ZAPISZ")}
            },
            dismissButton={TextButton(onClick={showEditor=false}){Text("ANULUJ")}}
        )
    }
}

@Composable
private fun NeonDial(progress: Float, accent: Color) {
    Canvas(Modifier.fillMaxSize()) {
        val r=min(size.width,size.height)*.44f
        val c=center
        drawCircle(Color.Black.copy(alpha=.50f),r,c)
        drawCircle(accent.copy(alpha=.10f),r+10.dp.toPx(),c,style=Stroke(16.dp.toPx()))
        drawCircle(Color(0xFF263030),r,c,style=Stroke(3.dp.toPx()))
        repeat(60){i->
            val a=Math.toRadians((i*6-90).toDouble())
            val inner=r-(if(i%5==0) 20.dp.toPx() else 12.dp.toPx())
            val outer=r-3.dp.toPx()
            drawLine(accent.copy(alpha=if(i%5==0).72f else .28f),
                Offset(c.x+cos(a).toFloat()*inner,c.y+sin(a).toFloat()*inner),
                Offset(c.x+cos(a).toFloat()*outer,c.y+sin(a).toFloat()*outer),
                strokeWidth=if(i%5==0) 2.dp.toPx() else 1.dp.toPx())
        }
        drawArc(accent,startAngle=-90f,sweepAngle=360f*progress,useCenter=false,
            topLeft=Offset(c.x-r,c.y-r),size=androidx.compose.ui.geometry.Size(r*2,r*2),
            style=Stroke(6.dp.toPx(),cap=StrokeCap.Round))
    }
}

@Composable
private fun AddedTimePanel(extra: Int, accent: Color) {
    val shape = RoundedCornerShape(18.dp)

    Box(
        Modifier
            .width(300.dp)
            .height(118.dp)
            .shadow(
                elevation = 26.dp,
                shape = shape,
                ambientColor = accent,
                spotColor = accent
            )
            .clip(shape)
            .background(Color(0xFF0A1118))
            .border(
                width = 2.dp,
                color = accent,
                shape = shape
            ),
        contentAlignment = Alignment.Center
    ) {
        Box(
            Modifier
                .matchParentSize()
                .border(
                    width = 5.dp,
                    color = accent.copy(alpha = 0.18f),
                    shape = shape
                )
        )

        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                "CZAS DOLICZONY",
                color = Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp
            )

            Text(
                "+${format(extra)}",
                color = accent,
                fontWeight = FontWeight.Black,
                fontSize = 50.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun RoundStartButton(running:Boolean,onClick:()->Unit) {
    val c=if(running) Color(0xFFFF1118) else Color(0xFF14D52D)
    Box(
        Modifier.size(92.dp).shadow(14.dp,CircleShape,ambientColor=c,spotColor=c)
            .clip(CircleShape).background(c).clickable(onClick=onClick),
        contentAlignment=Alignment.Center
    ){ Text(if(running)"Ⅱ" else "▶",color=Color.White,fontWeight=FontWeight.Black,fontSize=34.sp) }
}

@Composable
private fun SmallButton(text:String, modifier:Modifier=Modifier,onClick:()->Unit) {
    Box(modifier.height(68.dp).clip(RoundedCornerShape(12.dp))
        .background(Color(0xE6111919)).border(1.dp,Color(0xFF3C4747),RoundedCornerShape(12.dp))
        .clickable(onClick=onClick),contentAlignment=Alignment.Center) {
        Text(text,color=Color.White,fontWeight=FontWeight.Bold,textAlign=TextAlign.Center,fontSize=15.sp)
    }
}

@Composable
private fun HalfBar(first:Boolean,accent:Color) {
    Column(Modifier.fillMaxWidth().padding(horizontal=52.dp,vertical=18.dp)) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
            Text("I POŁOWA",color=if(first) Color(0xFF75FF31) else Color.White.copy(.65f),fontSize=12.sp)
            Text("II POŁOWA",color=if(!first) accent else Color.White.copy(.65f),fontSize=12.sp)
        }
        Spacer(Modifier.height(8.dp))
        Box(Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF36403C))){
            Box(Modifier.fillMaxWidth(if(first).5f else 1f).fillMaxHeight().background(if(first)Color(0xFF75FF31) else accent))
        }
    }
}

private fun format(sec:Int)=String.format("%02d:%02d",sec/60,sec%60)

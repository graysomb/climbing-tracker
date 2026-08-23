/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.example.inventory.ui.home

import android.annotation.SuppressLint
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import android.widget.Toast
import androidx.annotation.RequiresApi
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.twotone.Add
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.foundation.text.KeyboardOptions
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.room.Room
import androidx.room.RoomDatabase
import com.example.inventory.InventoryTopAppBar
import com.example.inventory.R
import com.example.inventory.data.Event
import com.example.inventory.data.Item
import com.example.inventory.ui.AppViewModelProvider
import com.example.inventory.ui.navigation.NavigationDestination
import com.example.inventory.ui.theme.InventoryTheme
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.charts.CombinedChart
import com.github.mikephil.charting.components.YAxis
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.data.CombinedData
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.formatter.ValueFormatter
import com.opencsv.CSVWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileWriter
import java.io.IOException
import java.io.OutputStreamWriter
import java.text.SimpleDateFormat
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.WeekFields
import java.util.Date
import java.util.Locale
import kotlin.collections.toDoubleArray
import kotlin.concurrent.read
import kotlin.math.log10
import kotlin.math.round
import kotlin.text.toDouble
import com.example.inventory.ui.home.LogisticFitter
import java.time.temporal.ChronoUnit
import kotlin.math.log
import kotlin.math.exp
import kotlin.math.pow
import kotlin.math.sqrt

object HomeDestination : NavigationDestination {
    override val route = "home"
    override val titleRes = R.string.app_name
}

/**
 * Entry route for Home screen
 */
@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("UnusedMaterial3ScaffoldPaddingParameter")
@Composable
fun HomeScreen(
    navigateToItemEntry: () -> Unit,
    navigateToItemUpdate: (Int) -> Unit,
    navigateToEventDetails: (Int) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: HomeViewModel = viewModel(factory = AppViewModelProvider.Factory)
) {
    val homeUiState by viewModel.homeUiState.collectAsState()

    Scaffold(
        modifier = modifier,
        topBar = {
            HomeTopBar(lastItemTime = homeUiState.lastItem.name, viewModel = viewModel)
        },
        floatingActionButton = {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Bottom,
                horizontalAlignment = Alignment.End
            ) {
                FloatingActionButton(
                    onClick = navigateToItemEntry,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.padding(dimensionResource(id = R.dimen.padding_large))
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = stringResource(R.string.item_entry_title)
                    )
                }
               /* FloatingActionButton(
                    onClick = navigateToItemEntry,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.padding(dimensionResource(id = R.dimen.padding_large))
                ) {
                    Icon(
                        imageVector = Icons.Default.AddCircle,
                        contentDescription = stringResource(R.string.item_entry_title)
                    )
                }*/
            }


        },
    ) { innerPadding ->
        HomeBody(
            itemList = homeUiState.itemList,
            eventList = homeUiState.eventList,
            onItemClick = navigateToItemUpdate,
            onEventClick = navigateToEventDetails,
            onEventSave = viewModel::addEvent,
            calculateStatistics = viewModel::getHomeCalculations,
            prepareVPointsChart = viewModel::getVPointsChartModel,
            modifier = modifier
                .padding(innerPadding)
                .fillMaxSize()
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeTopBar(lastItemTime: String, viewModel: HomeViewModel) {
    val currentTime by viewModel.currentTime.collectAsState()
    InventoryTopAppBar(
        title = TimeDifference.getFormattedDuration(currentTime, lastItemTime),
        canNavigateBack = false
    )
}


@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun HomeBody(
    itemList: List<Item>,
    eventList: List<Event>,
    onItemClick: (Int) -> Unit,
    onEventClick: (Int) -> Unit,
    onEventSave: (Event) -> Unit,
    calculateStatistics: suspend (List<Item>, Int) -> List<Float>,
    prepareVPointsChart: suspend (List<Item>, Boolean) -> VPointsChartModel,
    modifier: Modifier = Modifier
) {
    var plotByWeek by remember { mutableStateOf(false) }
    var moFilt by remember { mutableStateOf(0) }
    var locationFilter by remember { mutableStateOf(0) }
    var baselineMonths by remember { mutableStateOf(1) }
    var gradeProgressionDataByFilter by remember { mutableStateOf<Map<Int, GradeProgressionData>>(emptyMap()) }
    var gradeProgressionIsCalculating by remember { mutableStateOf(false) }
    val coroutineScope = rememberCoroutineScope()
    val pagerState = rememberPagerState()
    val filteredItems = remember(itemList, locationFilter) {
        when (locationFilter) {
            1 -> itemList.filter { it.outside == 0 }
            2 -> itemList.filter { it.outside == 1 }
            else -> itemList
        }
    }
    val calculatedCalcs by produceState<List<Float>?>(
        initialValue = null,
        filteredItems,
        baselineMonths
    ) {
        value = calculateStatistics(filteredItems, baselineMonths)
    }
    val filteredCalcs = calculatedCalcs ?: List(11) { 0f }
    val preparedVPointsChartState = produceState<VPointsChartModel?>(
        initialValue = null,
        filteredItems,
        plotByWeek
    ) {
        value = prepareVPointsChart(filteredItems, plotByWeek)
    }
    val locationFilterText = when (locationFilter) {
        1 -> "Inside"
        2 -> "Outside"
        else -> "Both"
    }
    val gradeProgressionData = gradeProgressionDataByFilter[locationFilter]

    fun writeCsvRows(csvWriter: CSVWriter, items: List<Item>, events: List<Event>) {
        val header = arrayOf("id", "time", "grade", "send/reps", "type", "weight", "outside", "effort", "pain", "fear")
        csvWriter.writeNext(header)

        items.forEach { item ->
            val row = arrayOf(
                item.id.toString(),
                item.name,
                item.price.toString(),
                item.quantity.toString(),
                item.type.toString(),
                item.weight.toString(),
                item.outside.toString(),
                item.effort.toString(),
                item.pain.toString(),
                item.fear.toString()
            )
            csvWriter.writeNext(row)
        }

        csvWriter.writeNext(arrayOf(""))
        csvWriter.writeNext(arrayOf("events"))
        csvWriter.writeNext(arrayOf("id", "time", "event_type", "note", "value"))
        events.forEach { event ->
            csvWriter.writeNext(
                arrayOf(
                    event.id.toString(),
                    event.time,
                    eventTypeLabel(event.type),
                    event.note,
                    event.value.toString()
                )
            )
        }
    }

    fun writeItemsToCsv(context: Context, items: List<Item>, events: List<Event>) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val resolver = context.contentResolver
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, "climb_data.csv")
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/csv")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }

                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                if (uri != null) {
                    val outputStream = resolver.openOutputStream(uri)
                        ?: throw IOException("Could not open Downloads file")
                    outputStream.use {
                        OutputStreamWriter(outputStream).use { writer ->
                            CSVWriter(writer).use { csvWriter ->
                                writeCsvRows(csvWriter, items, events)
                            }
                        }
                    }
                    Toast.makeText(context, "Exported climb_data.csv to Downloads", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "Could not create CSV export", Toast.LENGTH_SHORT).show()
                }
            } else {
                val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                val csvFile = File(downloadsDir, "climb_data.csv")
                CSVWriter(FileWriter(csvFile)).use { csvWriter ->
                    writeCsvRows(csvWriter, items, events)
                }
                Toast.makeText(context, "Exported climb_data.csv to Downloads", Toast.LENGTH_SHORT).show()
            }
        } catch (exception: IOException) {
            Toast.makeText(context, "CSV export failed: ${exception.message}", Toast.LENGTH_LONG).show()
        }
    }

    fun backupDatabaseToDownloads(context: Context) {
        val dbFile = context.getDatabasePath("item_database")

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val resolver = context.contentResolver
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, "my_database_backup.db")
                    put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }

                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                if (uri != null) {
                    val outputStream = resolver.openOutputStream(uri)
                        ?: throw IOException("Could not open Downloads file")
                    outputStream.use {
                        dbFile.inputStream().use { inputStream ->
                            inputStream.copyTo(outputStream)
                        }
                    }
                    Toast.makeText(context, "Backed up my_database_backup.db to Downloads", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "Could not create database backup", Toast.LENGTH_SHORT).show()
                }
            } else {
                val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                val backupFile = File(downloadsDir, "my_database_backup.db")
                dbFile.copyTo(backupFile, overwrite = true)
                Toast.makeText(context, "Backed up my_database_backup.db to Downloads", Toast.LENGTH_SHORT).show()
            }
        } catch (exception: IOException) {
            Toast.makeText(context, "Database backup failed: ${exception.message}", Toast.LENGTH_LONG).show()
        }
    }

    val context = LocalContext.current

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = modifier
    ) {
        if (itemList.isEmpty()) {
            Text(
                text = stringResource(R.string.no_item_description),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.titleLarge
            )
        } else {
            Row {
                Button(onClick = { plotByWeek = !plotByWeek }) {
                    Text(text = if (plotByWeek) "Week" else "Day")
                }
                Button(onClick = { locationFilter = (locationFilter + 1) % 3 }) {
                    Text(text = locationFilterText)
                }
                // New button for cycling integer state

            }
            HorizontalPager(
                pageCount = 4,
                state = pagerState,
                modifier = Modifier.weight(1f)
            ) { page ->
                when (page) {
                    0 -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        preparedVPointsChartState.value?.let { chartModel ->
                            ItemBarChart(
                                filteredItems,
                                Modifier.height(280.dp),
                                plotByWeek,
                                baselineMonths = baselineMonths,
                                preparedData = chartModel
                            )
                        } ?: Spacer(Modifier.height(280.dp))
                        Row(){
                            Text(" Sends/Day: " + ((filteredCalcs[1]*10f).toInt().toFloat()/10f).toString())
                            Text(" Trys/Day: "+((filteredCalcs[0]*10).toInt().toFloat()/10f).toString())
                        }
                        Row(){
                            Text(" Load: Today: " + ((filteredCalcs[5]*10f).toInt().toFloat()/10f).toString() + "%")
                            Text(" Week: " + ((filteredCalcs[6]*10f).toInt().toFloat()/10f).toString() + "%")
                            Text(" Month: " + ((filteredCalcs[7]*10f).toInt().toFloat()/10f).toString() + "%")
                        }
                        Row(){
                            Text(" ACWR: MV: " + ((filteredCalcs[8]*10f).toInt().toFloat()/10f).toString() + "%")
                            Text(" TV: " + ((filteredCalcs[9]*10f).toInt().toFloat()/10f).toString() + "%")
                            Text(" Injury: " + ((filteredCalcs[10]*10f).toInt().toFloat()/10f).toString() + "%")
                        }
                        Row(){
                            Text(" Flash: " + ((filteredCalcs[2]*1000f).toInt().toFloat()/1000f).toString())
                            Text(" Red: "+((filteredCalcs[3]*1000f).toInt().toFloat()/1000f).toString())
                            Text(" Proj: "+((filteredCalcs[4]*1000f).toInt().toFloat()/1000f).toString())
                        }
                        InventoryList(
                            itemList = filteredItems,
                            onItemClick = { onItemClick(it.id) },
                            modifier = Modifier.padding(horizontal = dimensionResource(id = R.dimen.padding_small))
                        )
                    }
                    1 -> EventPage(
                        eventList = eventList,
                        onEventClick = onEventClick,
                        onEventSave = onEventSave,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = dimensionResource(id = R.dimen.padding_small))
                    )
                    2 -> LazyColumn(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_medium)),
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = dimensionResource(id = R.dimen.padding_small))
                    ) {
                        item {
                            Row {
                                Button(onClick = { moFilt = (moFilt + 1) % 2 }) {
                                    Text(when (moFilt) {
                                        0 -> "all time"
                                        else -> "last 3 months"
                                    })
                                }
                            }
                        }
                        item {
                            preparedVPointsChartState.value?.let { chartModel ->
                                ItemBarChart(
                                    filteredItems,
                                    Modifier.height(280.dp),
                                    plotByWeek,
                                    showLoadOverlay = true,
                                    baselineMonths = baselineMonths,
                                    preparedData = chartModel
                                )
                            } ?: Spacer(Modifier.height(280.dp))
                        }
                        item {
                            VPointsMovingAverageChart(filteredItems, Modifier.height(280.dp))
                        }
                        item {
                            WeeklySentGradeChart(filteredItems, Modifier.height(280.dp))
                        }
                        item {
                            Button(
                                onClick = {
                                    if (!gradeProgressionIsCalculating) {
                                        val itemsForCalculation = filteredItems
                                        val filterForCalculation = locationFilter
                                        gradeProgressionIsCalculating = true
                                        coroutineScope.launch {
                                            val calculatedData = withContext(Dispatchers.Default) {
                                                calculateGradeProgressionData(itemsForCalculation)
                                            }
                                            gradeProgressionDataByFilter =
                                                gradeProgressionDataByFilter + (filterForCalculation to calculatedData)
                                            gradeProgressionIsCalculating = false
                                        }
                                    }
                                },
                                enabled = !gradeProgressionIsCalculating
                            ) {
                                Text(text = if (gradeProgressionData == null) "Calculate Flash/Red/Proj" else "Update Flash/Red/Proj")
                            }
                        }
                        if (gradeProgressionIsCalculating) {
                            item {
                                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                            }
                        }
                        gradeProgressionData?.let { data ->
                            item {
                                ItemGradeProgressionChart(data, Modifier.height(280.dp))
                            }
                        }
                        item {
                            ItemBarChartHP(filteredItems, Modifier.height(280.dp), plotByWeek)
                        }
                        item {
                            ItemBarChartProb(filteredItems, Modifier.height(280.dp), 0, moFilt)
                        }
                        item {
                            ItemBarChartProb(filteredItems, Modifier.height(280.dp), 1, moFilt)
                        }
                        item {
                            ItemBarChartProb(filteredItems, Modifier.height(280.dp), 2, moFilt)
                        }
                    }
                    else -> Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_medium)),
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(dimensionResource(id = R.dimen.padding_medium))
                    ) {
                        Text(
                            text = "Settings",
                            style = MaterialTheme.typography.titleLarge
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_small))
                        ) {
                            Button(onClick = { baselineMonths = (baselineMonths - 1).coerceAtLeast(1) }) {
                                Text(text = "-")
                            }
                            Text(
                                text = "Baseline: $baselineMonths mo",
                                style = MaterialTheme.typography.titleMedium
                            )
                            Button(onClick = { baselineMonths = (baselineMonths + 1).coerceAtMost(24) }) {
                                Text(text = "+")
                            }
                        }
                        Button(
                            onClick = { writeItemsToCsv(context, itemList, eventList) },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(text = "Export")
                        }
                        Button(
                            onClick = { backupDatabaseToDownloads(context) },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(text = "Backup")
                        }
                    }
                }
            }
        }
    }
}

private fun eventTypeLabel(type: Int): String {
    return when (type) {
        0 -> "Injury"
        1 -> "Bodyweight"
        2 -> "RPS"
        else -> "Event"
    }
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
private fun EventPage(
    eventList: List<Event>,
    onEventClick: (Int) -> Unit,
    onEventSave: (Event) -> Unit,
    modifier: Modifier = Modifier
) {
    var eventType by remember { mutableStateOf(0) }
    var injuryNote by remember { mutableStateOf("") }
    var bodyweight by remember { mutableStateOf("") }
    var rps by remember { mutableStateOf("0") }
    val context = LocalContext.current

    LazyColumn(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_medium)),
        modifier = modifier
    ) {
        item {
            Text(
                text = "Events",
                style = MaterialTheme.typography.titleLarge
            )
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_small))) {
                Button(onClick = { eventType = 0 }) {
                    Text(text = "Injury")
                }
                Button(onClick = { eventType = 1 }) {
                    Text(text = "Bodyweight")
                }
                Button(onClick = { eventType = 2 }) {
                    Text(text = "RPS")
                }
            }
        }
        item {
            Text(
                text = eventTypeLabel(eventType),
                style = MaterialTheme.typography.titleMedium
            )
        }

        item {
            when (eventType) {
                0 -> {
                    OutlinedTextField(
                        value = injuryNote,
                        onValueChange = { injuryNote = it },
                        label = { Text(text = "Injury note") },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            unfocusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            disabledContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                        ),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                1 -> {
                    OutlinedTextField(
                        value = bodyweight,
                        onValueChange = { value ->
                            bodyweight = value.filter { it.isDigit() || it == '.' }.take(6)
                        },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        label = { Text(text = "Bodyweight") },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            unfocusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            disabledContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
                2 -> {
                    OutlinedTextField(
                        value = rps,
                        onValueChange = { value ->
                            val digits = value.filter { it.isDigit() }.take(2)
                            rps = digits.toIntOrNull()?.coerceIn(0, 10)?.toString() ?: ""
                        },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        label = { Text(text = "RPS (0-10)") },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            unfocusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                            disabledContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
            }
        }

        item {
            Button(
                onClick = {
                    val now = LocalDateTime.now().toString()
                    val event = when (eventType) {
                        0 -> Event(time = now, type = 0, note = injuryNote.trim())
                        1 -> Event(time = now, type = 1, value = bodyweight.toDoubleOrNull() ?: 0.0)
                        else -> Event(time = now, type = 2, value = rps.toDoubleOrNull()?.coerceIn(0.0, 10.0) ?: 0.0)
                    }
                    onEventSave(event)
                    if (eventType == 0) injuryNote = ""
                    Toast.makeText(context, "Saved ${eventTypeLabel(eventType)}", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(text = "Save ${eventTypeLabel(eventType)}")
            }
        }

        items(eventList.take(20), key = { it.id }) { event ->
            EventListItem(
                event = event,
                modifier = Modifier.clickable { onEventClick(event.id) }
            )
        }
    }
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
private fun EventListItem(event: Event, modifier: Modifier = Modifier) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    Card(
        modifier = modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(dimensionResource(id = R.dimen.padding_large)),
            verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_small))
        ) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = LocalDateTime.parse(event.time, formatter).format(DateTimeFormatter.ofPattern("MM-dd HH:mm")),
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(Modifier.weight(1f))
                Text(
                    text = eventTypeLabel(event.type),
                    style = MaterialTheme.typography.titleMedium
                )
            }
            val detail = when (event.type) {
                0 -> event.note
                1 -> event.value.toString()
                2 -> event.value.toInt().toString()
                else -> ""
            }
            if (detail.isNotBlank()) {
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }
    }
}


internal fun calculateHomeCalcs(itemList: List<Item>, baselineMonths: Int): List<Float> {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val currentDate = LocalDate.now()
    val injuryTotalVPointsAcwrMean = 0.5084f
    val injuryTotalVPointsAcwrVariance = 0.0603f
    val injuryAverageVPointsAcwrMean = 1.9742f
    val injuryAverageVPointsAcwrVariance = 1.0113f
    val baselineMonthCount = baselineMonths.coerceAtLeast(1).toLong()
    val baselineStartDate = currentDate.minusMonths(baselineMonthCount)
    val gradeEstimateStartDate = currentDate.minusMonths(3)
    val climbItems = itemList.filter { it.type == 0 }
    val earliestClimbDate = climbItems.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    }

    val filteredItems = climbItems.filter { item ->
        val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
        !itemDate.isBefore(baselineStartDate) && !itemDate.isAfter(currentDate)
    }

    val gradeEstimateItems = climbItems.filter { item ->
        val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
        !itemDate.isBefore(gradeEstimateStartDate) && !itemDate.isAfter(currentDate)
    }

    val groupedQuantities = filteredItems.groupBy { item ->
        LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
    }

    val dailyQuantities = groupedQuantities.mapValues { (_, itemsForPeriod) ->
        val sendsLoad = itemsForPeriod.filter { it.quantity > 0 }.sumOf { it.price.toInt() }
        val triesLoad = sendsLoad + itemsForPeriod.filter { it.quantity == 0 }.sumOf { it.price.toInt() }
        listOf(sendsLoad.toFloat(), triesLoad.toFloat())
    }

    val sends = dailyQuantities.values.map { it[0] }
    val tries = dailyQuantities.values.map { it[1] }
    val sendsPerDay = sends.filter { it != 0f }.let { if (it.isNotEmpty()) it.average().toFloat() else 0f }
    val triesPerDay = tries.filter { it != 0f }.let { if (it.isNotEmpty()) it.average().toFloat() else 0f }

    fun loadingComponent(currentLoad: Float, baselineLoad: Float): Float {
        return if (baselineLoad > 0f) currentLoad / baselineLoad else 0f
    }

    fun triesLoadForItems(items: List<Item>): Float {
        return items.sumOf { it.price.toInt() }.toFloat()
    }

    fun climbItemsForDay(date: LocalDate): List<Item> {
        return climbItems.filter { item ->
            LocalDateTime.parse(item.name, formatter).toLocalDate() == date
        }
    }

    fun datesInTrailingWindow(endDate: LocalDate, windowDays: Long): List<LocalDate> {
        return (windowDays - 1 downTo 0).map { daysAgo -> endDate.minusDays(daysAgo) }
    }

    fun loadPercentForWindow(endDate: LocalDate, windowDays: Long): Float {
        val windowStart = endDate.minusDays(windowDays - 1)
        val baselineStart = windowStart.minusMonths(baselineMonthCount)
        val effectiveBaselineStart = earliestClimbDate?.let { earliestDate ->
            if (baselineStart.isAfter(earliestDate)) baselineStart else earliestDate
        } ?: baselineStart
        val baselineItems = climbItems.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(effectiveBaselineStart) && itemDate.isBefore(windowStart)
        }
        val baselineDayCount = if (windowDays == 1L) {
            baselineItems
                .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
                .count { (_, itemsForDay) -> triesLoadForItems(itemsForDay) > 0f }
                .toFloat()
        } else {
            ChronoUnit.DAYS.between(effectiveBaselineStart, windowStart).toFloat()
        }
        val baselineTriesPerDay = if (baselineDayCount > 0f) {
            triesLoadForItems(baselineItems) / baselineDayCount
        } else {
            0f
        }
        val windowItems = climbItems.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(windowStart) && !itemDate.isAfter(endDate)
        }
        val windowLoad = triesLoadForItems(windowItems)

        return loadingComponent(windowLoad, baselineTriesPerDay * windowDays.toFloat()) * 100f
    }

    fun totalVPointsForWindow(endDate: LocalDate, windowDays: Long): Float {
        val windowStart = endDate.minusDays(windowDays - 1)
        return triesLoadForItems(climbItems.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(windowStart) && !itemDate.isAfter(endDate)
        })
    }

    fun meanDailyAverageVPointsForWindow(endDate: LocalDate, windowDays: Long): Float {
        val dailyAverages = datesInTrailingWindow(endDate, windowDays).map { date ->
            val itemsForDay = climbItemsForDay(date)
            if (itemsForDay.isNotEmpty()) triesLoadForItems(itemsForDay) / itemsForDay.size else 0f
        }
        return if (dailyAverages.isNotEmpty()) dailyAverages.average().toFloat() else 0f
    }

    val loadingThisDay = loadPercentForWindow(currentDate, 1)
    val loadingThisWeek = loadPercentForWindow(currentDate, 7)
    val currentMonthStart = currentDate.withDayOfMonth(1)
    val previousMonthStart = currentMonthStart.minusMonths(1)
    val currentMonthLoad = triesLoadForItems(climbItems.filter { item ->
        val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
        !itemDate.isBefore(currentMonthStart) && !itemDate.isAfter(currentDate)
    })
    val previousMonthLoad = triesLoadForItems(climbItems.filter { item ->
        val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
        !itemDate.isBefore(previousMonthStart) && itemDate.isBefore(currentMonthStart)
    })
    val loadingThisMonth = loadingComponent(currentMonthLoad, previousMonthLoad) * 100f
    val totalVPointsAcwr = loadingComponent(
        totalVPointsForWindow(currentDate, 7),
        totalVPointsForWindow(currentDate, 28)
    )
    val averageVPointsAcwr = loadingComponent(
        meanDailyAverageVPointsForWindow(currentDate, 7),
        meanDailyAverageVPointsForWindow(currentDate, 28)
    )
    val totalVPointsAcwrPercent = loadingComponent(totalVPointsAcwr, injuryTotalVPointsAcwrMean) * 100f
    val averageVPointsAcwrPercent = loadingComponent(averageVPointsAcwr, injuryAverageVPointsAcwrMean) * 100f
    val totalVPointsZScore = if (injuryTotalVPointsAcwrVariance > 0f) {
        (totalVPointsAcwr - injuryTotalVPointsAcwrMean) / sqrt(injuryTotalVPointsAcwrVariance)
    } else {
        0f
    }
    val averageVPointsZScore = if (injuryAverageVPointsAcwrVariance > 0f) {
        (averageVPointsAcwr - injuryAverageVPointsAcwrMean) / sqrt(injuryAverageVPointsAcwrVariance)
    } else {
        0f
    }
    val injuryProbabilityPercent = (
        exp(
            -0.5f * (
                totalVPointsZScore * totalVPointsZScore +
                    averageVPointsZScore * averageVPointsZScore
                )
        ) * 100f
        ).coerceIn(0f, 100f)

    val groupedByPrice = gradeEstimateItems.groupBy { it.price }
    val priceFractions = groupedByPrice.mapValues { (_, items) ->
        val sendsForPrice = items.count { it.quantity > 0 }
        val attempts = items.count { it.quantity <= 0 }
        if (sendsForPrice + attempts > 0) sendsForPrice.toFloat() / (sendsForPrice + attempts) else 0f
    }

    val xValues = priceFractions.keys.map { it.toFloat() }
    val yValues = priceFractions.values.toList()
    val paramsFit = if (xValues.isNotEmpty() && yValues.isNotEmpty()) {
        val xValuesJava = xValues.map { it.toDouble() }.toDoubleArray()
        val yValuesJava = yValues.map { it.toDouble() }.toDoubleArray()
        LogisticFitter.fitLogistic(xValuesJava, yValuesJava).toList()
    } else {
        listOf(0.0, 0.0, 0.0)
    }
    val a = paramsFit[0].toFloat()
    val b = paramsFit[1].toFloat()
    val c = paramsFit[2].toFloat()
    val send50 = if (a > 0.5f && b != 0f) {
        (b * c - log((-1 + 2 * a).toDouble(), Math.exp(1.0))) / b
    } else {
        0.0
    }
    val p3 = 0.206299
    val p12 = 0.0561257
    val send3try = if (a > p3 && b != 0f) {
        (b * c - log(((a - p3) / p3).toDouble(), Math.exp(1.0))) / b
    } else {
        0.0
    }
    val send6try = if (a > p12 && b != 0f) {
        (b * c - log(((a - p12) / p12).toDouble(), Math.exp(1.0))) / b
    } else {
        0.0
    }

    return listOf(
        triesPerDay,
        sendsPerDay,
        send50.toFloat(),
        send3try.toFloat(),
        send6try.toFloat(),
        loadingThisDay,
        loadingThisWeek,
        loadingThisMonth,
        averageVPointsAcwrPercent,
        totalVPointsAcwrPercent,
        injuryProbabilityPercent
    )
}

@RequiresApi(Build.VERSION_CODES.O)
private fun rollingLoadEntries(
    itemList: List<Item>,
    earliestDate: LocalDate,
    plotByWeek: Boolean,
    baselineMonths: Int
): List<Entry> {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val baselineMonthCount = baselineMonths.coerceAtLeast(1).toLong()
    val dailyLoadByDate = itemList
        .asSequence()
        .filter { it.type == 0 }
        .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
        .mapValues { (_, itemsForDay) -> itemsForDay.sumOf { it.price }.toFloat() }

    fun loadComponent(currentLoad: Float, baselineLoad: Float): Float {
        return if (baselineLoad > 0f) currentLoad / baselineLoad else 0f
    }

    val latestDate = dailyLoadByDate.keys.maxOrNull() ?: return emptyList()
    val dayCount = ChronoUnit.DAYS.between(earliestDate, latestDate).toInt() + 1
    val prefixLoads = FloatArray(dayCount + 1)
    for (dayIndex in 0 until dayCount) {
        prefixLoads[dayIndex + 1] =
            prefixLoads[dayIndex] + (dailyLoadByDate[earliestDate.plusDays(dayIndex.toLong())] ?: 0f)
    }

    fun dayIndex(date: LocalDate): Int =
        ChronoUnit.DAYS.between(earliestDate, date).toInt().coerceIn(0, dayCount)

    fun loadBetween(startInclusive: LocalDate, endExclusive: LocalDate): Float {
        val startIndex = dayIndex(startInclusive)
        val endIndex = dayIndex(endExclusive)
        return prefixLoads[endIndex] - prefixLoads[startIndex]
    }

    return (0 until dayCount).mapNotNull { endIndex ->
        val endDate = earliestDate.plusDays(endIndex.toLong())
        val windowStart = endDate.minusDays(6).let { if (it.isAfter(earliestDate)) it else earliestDate }
        val requestedBaselineStart = windowStart.minusMonths(baselineMonthCount)
        val effectiveBaselineStart =
            if (requestedBaselineStart.isAfter(earliestDate)) requestedBaselineStart else earliestDate
        val previousDayCount = ChronoUnit.DAYS.between(effectiveBaselineStart, windowStart).toFloat()
        val previousTriesPerDay = if (previousDayCount > 0f) {
            loadBetween(effectiveBaselineStart, windowStart) / previousDayCount
        } else 0f
        val windowTriesLoad = loadBetween(windowStart, endDate.plusDays(1))
        val rollingLoadPercent = loadComponent(windowTriesLoad, previousTriesPerDay * 7f) * 100f

        if (previousTriesPerDay > 0f) {
            val daysSinceEarliest = ChronoUnit.DAYS.between(earliestDate, endDate).toFloat()
            val x = if (plotByWeek) daysSinceEarliest / 7f else daysSinceEarliest
            Entry(x, rollingLoadPercent)
        } else {
            null
        }
    }.sortedBy { it.x }.toList()
}



@Composable
private fun InventoryList(
    itemList: List<Item>, onItemClick: (Item) -> Unit, modifier: Modifier = Modifier
) {
    LazyColumn(modifier = modifier) {
        items(items = itemList, key = { it.id }) { item ->
            InventoryItem(item = item,
                modifier = Modifier
                    .padding(dimensionResource(id = R.dimen.padding_small))
                    .clickable { onItemClick(item) })
        }
    }
}

@Composable
private fun InventoryItem(
    item: Item, modifier: Modifier = Modifier
) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    Card(
        modifier = modifier, elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(dimensionResource(id = R.dimen.padding_large)),
            verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_small))
        ) {
            Row(
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = LocalDateTime.parse(item.name, formatter).format(DateTimeFormatter.ofPattern("MM-dd")),
                    style = MaterialTheme.typography.titleLarge,
                )
                Spacer(Modifier.weight(1f))
                if (item.type<1) {
                    Text(
                        text = stringResource(R.string.v, item.price),
                        style = MaterialTheme.typography.titleMedium
                    )
                }else{
                    Text(
                        text = stringResource(R.string.weight_val , item.weight.toInt()),
                        style = MaterialTheme.typography.titleMedium
                    )
                }
            }
            Row(modifier = modifier.fillMaxWidth()) {
                fun typeCast(Type: Int): String {
                    if (Type == 0) {
                        return "Climb"
                    } else if (Type == 1) {
                        return "Hang"
                    } else if (Type == 2) {
                        return "Pull"
                    } else {
                        return "Other"
                    }
                }
                    Text(
                    text = stringResource(if(item.type<1){R.string.in_stock} else {R.string.rep_val}, item.quantity),
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                        text = typeCast(item.type),
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(start = 20.dp)
                    )

            }
        }
    }
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChartProb2(itemList: List<Item>, modifier: Modifier = Modifier, integerState: Int, moFilt: Int) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val currentDate = LocalDate.now()
    val threeMonthsAgo = currentDate.minusMonths(3)

    val filteredItems = itemList.filter { item ->
        val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
        !itemDate.isBefore(threeMonthsAgo) && !itemDate.isAfter(currentDate)
    }

    var groupedByPrice = filteredItems.groupBy { it.price }

    if (moFilt == 0) {
        groupedByPrice = itemList.groupBy { it.price }
    }


    val priceFractions = groupedByPrice.mapValues { (_, items) ->
        val sends = items.count { it.quantity > 0 }
        val sendsV = items.filter{ it.quantity > 0 }.sumOf{it.price.toInt()}
        val attempts = items.count { it.quantity <= 0 }
        when (integerState) {
            0 -> if (sends + attempts > 0) sends.toFloat() / (sends + attempts) else 0f
            1 -> sendsV.toFloat()
            2 -> (sends + attempts).toFloat()
            else -> 0f
        }
    }

    val fractionEntries = priceFractions.map { (price, fraction) ->
        BarEntry(price.toFloat(), fraction)
    }
    val txt = when (integerState) {
        1 -> "V Points Sent Per Grade"
        2 -> "Total Attempts"
        else -> "Probability of Sends Per Grade"
    }

    val fractionDataSet = BarDataSet(fractionEntries, txt).apply {
        color = Color.CYAN
    }

    val filteredItemsDay = itemList
    // Group items by week or day
    val groupedQuantities =
        filteredItemsDay.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
        }

    val dailyQuantities = groupedQuantities.mapValues { (_, itemsForPeriod) ->
        val zeroQuantitySum = itemsForPeriod.filter { it.quantity > 0 }.sumOf { it.price.toInt() }
        val positiveQuantitySum = itemsForPeriod.filter { it.quantity == 0 }.sumOf { it.price.toInt() }
        listOf(zeroQuantitySum.toFloat(),positiveQuantitySum.toFloat()) // maybe add a multiplier for no sends
    }
    val sends = dailyQuantities.values.sumOf { it[0].toDouble() }
    val trys = dailyQuantities.values.sumOf { it[1].toDouble() }
    val count = dailyQuantities.size
    var minVariance = Float.MAX_VALUE

    val startA = 0f // Starting point of the search for 'a'
    val endA = 10.0f // Ending point of the search for 'a'
    val step = 0.01f // Step size for 'a'

    val optimalA = generateSequence(startA) { prev ->
        if (prev + step <= endA) prev + step else null
    }.minOfOrNull { coefficientA ->
        val variance = sends.toFloat() + trys.toFloat() / coefficientA
        variance
    } ?: startA // Handle case where range is empty

    val meanVPerDay = (sends.toFloat() +trys.toFloat() / optimalA)/count

    // Fit the data to c / (exp((x - a) / b) + 1) using least squares
    val xValues = priceFractions.keys.map { it.toFloat() }
    val yValues = priceFractions.values.toList()
    val fitEntries = mutableListOf<Entry>()
    val fittedYValues = mutableListOf<Float>()

    if (xValues.isNotEmpty() && yValues.isNotEmpty() && integerState==0) {
        val initialA = xValues.average().toFloat()
        val initialB = (xValues.maxOrNull()!! - xValues.minOrNull()!!) / 8
        val initialC = yValues.maxOrNull() ?: 1f

        // Convert Kotlin collections to Java arrays
        val xValuesJava = xValues.map { it.toDouble() }.toDoubleArray()
        val yValuesJava = yValues.map { it.toDouble() }.toDoubleArray()

        // Perform least squares fitting using the Java class LogisticFitter
        val parameters = LogisticFitter.fitLogistic(xValuesJava, yValuesJava)
        val (a, b, c) = (parameters.toList())

        xValues.sorted().forEach { x ->
            val y = a / (Math.exp((-b*(x - c)).toDouble()) + 1).toFloat()
            fitEntries.add(Entry(x, y.toFloat()))
            fittedYValues.add(y.toFloat())
        }
    }


    val fittedtryValues = mutableListOf<Float>()
    fittedYValues.map { y ->
            if (y <= 0.0) {
                // Handle edge cases: y = 0 or y = 1
                val n = 0.0 // or an appropriate sentinel value
                fittedtryValues.add(n.toFloat())
            }
            if (y >= 1.0) {
                val n=1.0
                fittedtryValues.add(n.toFloat())
            } else {
                val n = log(0.5,10.0) / log(1 - y.toDouble(),10.0)
                fittedtryValues.add(n.toFloat())
            }

        }

    val tryValues = mutableListOf<Float>()
    yValues.map { y ->
        if (y <= 0.0) {
            // Handle edge cases: y = 0 or y = 1
            val n = 0.0 // or an appropriate sentinel value
            tryValues.add(n.toFloat())
        }
        if (y >= 1.0) {
            val n=1.0
            tryValues.add(n.toFloat())
        } else {
            val n = log(0.5,10.0) / log(1 - y.toDouble(),10.0)
            tryValues.add(n.toFloat())
        }

    }

    val tryFitEntries = mutableListOf<Entry>()
    val tryEntries = mutableListOf<BarEntry>()
    for (i in xValues.indices) {
        val x = xValues[i]
        val y = tryValues[i]

        // Add to the respective lists
        tryFitEntries.add(Entry(x, y)) // Replace 'y' with a calculated fit value if necessary
        tryEntries.add(BarEntry(x, y))
    }

    val tryDataSet = BarDataSet(tryEntries, txt).apply {
        color = Color.CYAN
    }

    val barData = BarData(tryDataSet)
    barData.isHighlightEnabled = false
    barData.setDrawValues(false)

    val lineDataSet = LineDataSet(tryFitEntries, "Fit Curve").apply {
        color = android.graphics.Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.MAGENTA
        valueTextSize = 12f
    }


    val lineData = LineData(lineDataSet)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = android.graphics.Color.CYAN

                this.data = CombinedData().apply {
                    setData(barData)
                    setData(lineData)
                }

                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = android.graphics.Color.CYAN

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return "${value.toInt()}"
                    }
                }
            }
        },
        update = { barChart ->
            barChart.data = CombinedData().apply {
                setData(barData)
                setData(lineData)
            }
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChartProb(itemList: List<Item>, modifier: Modifier = Modifier, integerState: Int, moFilt: Int) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val currentDate = LocalDate.now()
    val threeMonthsAgo = currentDate.minusMonths(3)
    val chartKey = "prob-${itemList.hashCode()}-$integerState-$moFilt"

    val filteredItems = remember(itemList, threeMonthsAgo, currentDate) {
        itemList.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(threeMonthsAgo) && !itemDate.isAfter(currentDate)
        }
    }

    val groupedByPrice = remember(itemList, filteredItems, moFilt) {
        if (moFilt == 0) {
            itemList.groupBy { it.price }
        } else {
            filteredItems.groupBy { it.price }
        }
    }


    val priceFractions = remember(groupedByPrice, integerState) {
        groupedByPrice.mapValues { (_, items) ->
            val sends = items.count { it.quantity > 0 }
            val sendsV = items.filter { it.quantity > 0 }.sumOf { it.price.toInt() }
            val attempts = items.count { it.quantity <= 0 }
            when (integerState) {
                0 -> if (sends + attempts > 0) sends.toFloat() / (sends + attempts) else 0f
                1 -> sendsV.toFloat()
                2 -> (sends + attempts).toFloat()
                else -> 0f
            }
        }
    }

    val fractionEntries = priceFractions.map { (price, fraction) ->
        BarEntry(price.toFloat(), fraction)
    }
    val txt = when (integerState) {
        1 -> "V Points Sent Per Grade"
        2 -> "Total Attempts"
        else -> "Probability of Sends Per Grade"
    }

    val fractionDataSet = BarDataSet(fractionEntries, txt).apply {
        color = Color.CYAN
    }

    val barData = BarData(fractionDataSet)
    barData.isHighlightEnabled = false
    barData.setDrawValues(false)

    // Fit the data to c / (exp((x - a) / b) + 1) using least squares
    val xValues = priceFractions.keys.map { it.toFloat() }
    val yValues = priceFractions.values.toList()
    val fitEntries = mutableListOf<Entry>()

    if (xValues.isNotEmpty() && yValues.isNotEmpty() && integerState==0) {
        val initialA = xValues.average().toFloat()
        val initialB = (xValues.maxOrNull()!! - xValues.minOrNull()!!) / 8
        val initialC = yValues.maxOrNull() ?: 1f

        // Convert Kotlin collections to Java arrays
        val xValuesJava = xValues.map { it.toDouble() }.toDoubleArray()
        val yValuesJava = yValues.map { it.toDouble() }.toDoubleArray()

        // Perform least squares fitting using the Java class LogisticFitter
        val parameters = LogisticFitter.fitLogistic(xValuesJava, yValuesJava)
        val (a, b, c) = (parameters.toList())

        xValues.sorted().forEach { x ->
            val y = a / (Math.exp((-b*(x - c)).toDouble()) + 1).toFloat()
            fitEntries.add(Entry(x, y.toFloat()))
        }
    }

    val lineDataSet = LineDataSet(fitEntries, "Fit Curve").apply {
        color = android.graphics.Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.MAGENTA
        valueTextSize = 12f
    }

    val lineData = LineData(lineDataSet)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = android.graphics.Color.CYAN

                data = CombinedData().apply {
                    setData(barData)
                    setData(lineData)
                }

                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = android.graphics.Color.CYAN

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return "${value.toInt()}"
                    }
                }
            }
        },
        update = { barChart ->
            if (barChart.tag == chartKey) return@AndroidView
            barChart.tag = chartKey
            barChart.data = CombinedData().apply {
                setData(barData)
                setData(lineData)
            }
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}


@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun WeeklySentGradeChart(itemList: List<Item>, modifier: Modifier = Modifier) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val chartKey = "weekly-sent-${itemList.hashCode()}"
    val sentClimbs = remember(itemList) {
        itemList
            .filter { it.type == 0 && it.quantity > 0 }
            .sortedBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
    }
    val earliestDate = sentClimbs.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: LocalDate.now()

    val groupedByWeek = remember(sentClimbs, earliestDate) {
        sentClimbs.groupBy { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            (ChronoUnit.DAYS.between(earliestDate, itemDate) / 7L).toFloat()
        }
    }

    val maxEntries = groupedByWeek.map { (week, items) ->
        Entry(week, items.maxOf { it.price }.toFloat())
    }.sortedBy { it.x }

    val averageEntries = groupedByWeek.map { (week, items) ->
        Entry(week, items.map { it.price }.average().toFloat())
    }.sortedBy { it.x }

    val maxDataSet = LineDataSet(maxEntries, "Max sent").apply {
        color = Color.CYAN
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = Color.CYAN
        valueTextSize = 10f
    }
    val averageDataSet = LineDataSet(averageEntries, "Avg sent").apply {
        color = Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = Color.MAGENTA
        valueTextSize = 10f
    }
    val lineData = remember(maxEntries, averageEntries) {
        LineData(maxDataSet, averageDataSet).apply {
            setDrawValues(false)
        }
    }

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = Color.CYAN
                data = CombinedData().apply {
                    setData(lineData)
                }
                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = Color.CYAN
                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val date = earliestDate.plusDays(value.toLong() * 7L)
                        return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                    }
                }
            }
        },
        update = { chart ->
            if (chart.tag == chartKey) return@AndroidView
            chart.tag = chartKey
            chart.data = CombinedData().apply {
                setData(lineData)
            }
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    val date = earliestDate.plusDays(value.toLong() * 7L)
                    return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                }
            }
            chart.notifyDataSetChanged()
            chart.invalidate()
        }
    )
}


@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun VPointsMovingAverageChart(itemList: List<Item>, modifier: Modifier = Modifier) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    var defaultViewportKey by remember { mutableStateOf<String?>(null) }
    val chartKey = "vpoints-ma-${itemList.hashCode()}"
    val climbItems = remember(itemList) {
        itemList
            .filter { it.type == 0 }
            .sortedBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
    }
    val earliestDate = climbItems.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: LocalDate.now()
    val latestDate = climbItems.maxOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: earliestDate
    val dailyVPoints = remember(climbItems) {
        climbItems
            .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
            .mapValues { (_, itemsForDay) ->
                itemsForDay.sumOf { it.price.toInt() }.toFloat()
            }
    }
    val dayCount = ChronoUnit.DAYS.between(earliestDate, latestDate).toInt() + 1
    val prefixVPoints = remember(dailyVPoints, earliestDate, latestDate) {
        FloatArray(dayCount + 1).also { prefix ->
            for (dayIndex in 0 until dayCount) {
                val date = earliestDate.plusDays(dayIndex.toLong())
                prefix[dayIndex + 1] = prefix[dayIndex] + (dailyVPoints[date] ?: 0f)
            }
        }
    }

    fun movingAverageEntries(windowDays: Long): List<Entry> {
        val windowSize = windowDays.toInt()
        return (0 until dayCount).map { endIndex ->
            val startIndex = (endIndex - windowSize + 1).coerceAtLeast(0)
            val daysInWindow = endIndex - startIndex + 1
            val windowVPoints = prefixVPoints[endIndex + 1] - prefixVPoints[startIndex]
            Entry(endIndex.toFloat(), windowVPoints / daysInWindow.toFloat())
        }
    }

    val sevenDayEntries = remember(dailyVPoints, earliestDate, latestDate) { movingAverageEntries(7) }
    val thirtyDayEntries = remember(dailyVPoints, earliestDate, latestDate) { movingAverageEntries(30) }
    val ninetyDayEntries = remember(dailyVPoints, earliestDate, latestDate) { movingAverageEntries(90) }

    val sevenDayDataSet = LineDataSet(sevenDayEntries, "7d avg").apply {
        color = android.graphics.Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.MAGENTA
        valueTextSize = 10f
    }
    val thirtyDayDataSet = LineDataSet(thirtyDayEntries, "30d avg").apply {
        color = android.graphics.Color.YELLOW
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.YELLOW
        valueTextSize = 10f
    }
    val ninetyDayDataSet = LineDataSet(ninetyDayEntries, "90d avg").apply {
        color = android.graphics.Color.CYAN
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.CYAN
        valueTextSize = 10f
    }
    val lineData = remember(sevenDayEntries, thirtyDayEntries, ninetyDayEntries) {
        LineData(sevenDayDataSet, thirtyDayDataSet, ninetyDayDataSet).apply {
            setDrawValues(false)
        }
    }
    val viewportKey = "${lineData.xMin}-${lineData.xMax}"
    val defaultVisibleDays = 90f

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = Color.CYAN
                axisRight.isEnabled = false
                data = CombinedData().apply {
                    setData(lineData)
                }
                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = Color.CYAN
                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val date = earliestDate.plusDays(value.toLong())
                        return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                    }
                }
            }
        },
        update = { chart ->
            if (chart.tag == chartKey) return@AndroidView
            chart.tag = chartKey
            chart.data = CombinedData().apply {
                setData(lineData)
            }
            chart.axisRight.isEnabled = false
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    val date = earliestDate.plusDays(value.toLong())
                    return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                }
            }
            chart.notifyDataSetChanged()
            if (defaultViewportKey != viewportKey) {
                defaultViewportKey = viewportKey
                chart.fitScreen()
                val xRange = lineData.xMax - lineData.xMin
                if (xRange > defaultVisibleDays) {
                    chart.zoom(xRange / defaultVisibleDays, 1f, lineData.xMax, 0f)
                    chart.moveViewToX(lineData.xMax)
                }
            }
            chart.invalidate()
        }
    )
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun LoadDebugChart(itemList: List<Item>, modifier: Modifier = Modifier, baselineMonths: Int) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val baselineMonthCount = baselineMonths.coerceAtLeast(1).toLong()
    val climbItems = itemList
        .filter { it.type == 0 }
        .sortedBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
    val earliestDate = climbItems.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: LocalDate.now()

    data class DailyLoad(val date: LocalDate, val triesLoad: Float)

    val dailyLoads = climbItems
        .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
        .map { (date, itemsForDay) ->
            DailyLoad(date, itemsForDay.sumOf { it.price.toInt() }.toFloat())
        }
        .sortedBy { it.date }

    val dailyLoadByDate = dailyLoads.associateBy { it.date }
    val latestDate = dailyLoads.maxOfOrNull { it.date } ?: earliestDate
    val numeratorEntries = mutableListOf<Entry>()
    val denominatorEntries = mutableListOf<Entry>()

    generateSequence(earliestDate) { date ->
        val nextDate = date.plusDays(1)
        if (!nextDate.isAfter(latestDate)) nextDate else null
    }.forEach { endDate ->
        val windowStart = endDate.minusDays(6)
        val baselineStart = windowStart.minusMonths(baselineMonthCount)
        val effectiveBaselineStart = if (baselineStart.isAfter(earliestDate)) {
            baselineStart
        } else {
            earliestDate
        }
        val previousLoads = dailyLoads.filter { load ->
            !load.date.isBefore(effectiveBaselineStart) && load.date.isBefore(windowStart)
        }
        val previousDayCount = ChronoUnit.DAYS.between(effectiveBaselineStart, windowStart).toFloat()
        if (previousDayCount > 0f) {
            val previousTriesPerDay = previousLoads.sumOf { it.triesLoad.toDouble() }.toFloat() / previousDayCount
            if (previousTriesPerDay > 0f) {
                val windowDates = generateSequence(windowStart) { date ->
                    val nextDate = date.plusDays(1)
                    if (!nextDate.isAfter(endDate)) nextDate else null
                }.toList()
                val numerator = windowDates.sumOf { date ->
                    (dailyLoadByDate[date]?.triesLoad ?: 0f).toDouble()
                }.toFloat()
                val denominator = previousTriesPerDay * 7f
                val x = ChronoUnit.DAYS.between(earliestDate, endDate).toFloat()
                numeratorEntries.add(Entry(x, numerator))
                denominatorEntries.add(Entry(x, denominator))
            }
        }
    }

    val numeratorDataSet = LineDataSet(numeratorEntries, "Load numerator").apply {
        color = android.graphics.Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.MAGENTA
        valueTextSize = 10f
    }
    val denominatorDataSet = LineDataSet(denominatorEntries, "Load denominator").apply {
        color = android.graphics.Color.YELLOW
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.YELLOW
        valueTextSize = 10f
    }
    val lineData = LineData(numeratorDataSet, denominatorDataSet)
    lineData.setDrawValues(false)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = Color.CYAN
                axisRight.isEnabled = false
                data = CombinedData().apply {
                    setData(lineData)
                }
                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = Color.CYAN
                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val date = earliestDate.plusDays(value.toLong())
                        return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                    }
                }
            }
        },
        update = { chart ->
            chart.data = CombinedData().apply {
                setData(lineData)
            }
            chart.axisRight.isEnabled = false
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    val date = earliestDate.plusDays(value.toLong())
                    return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                }
            }
            chart.notifyDataSetChanged()
            chart.invalidate()
        }
    )
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun WeeklyLoadChart(itemList: List<Item>, modifier: Modifier = Modifier, baselineMonths: Int) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val baselineMonthCount = baselineMonths.coerceAtLeast(1).toLong()
    val climbItems = itemList
        .filter { it.type == 0 }
        .sortedBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
    val earliestDate = climbItems.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: LocalDate.now()

    data class DailyLoad(val date: LocalDate, val sendsLoad: Float, val triesLoad: Float)

    val dailyLoads = climbItems
        .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
        .map { (date, itemsForDay) ->
            val sendsLoad = itemsForDay.filter { it.quantity > 0 }.sumOf { it.price.toInt() }.toFloat()
            val triesLoad = sendsLoad + itemsForDay.filter { it.quantity == 0 }.sumOf { it.price.toInt() }.toFloat()
            DailyLoad(date, sendsLoad, triesLoad)
        }
        .sortedBy { it.date }

    fun loadComponent(currentLoad: Float, baselineLoad: Float): Float {
        return if (baselineLoad > 0f) currentLoad / baselineLoad else 0f
    }

    val dailyLoadByDate = dailyLoads.associateBy { it.date }
    val latestDate = dailyLoads.maxOfOrNull { it.date } ?: earliestDate
    val rollingEntries = generateSequence(earliestDate) { date ->
        val nextDate = date.plusDays(1)
        if (!nextDate.isAfter(latestDate)) nextDate else null
    }.mapNotNull { endDate ->
            val windowStart = endDate.minusDays(6)
            val baselineStart = windowStart.minusMonths(baselineMonthCount)
            val effectiveBaselineStart = if (baselineStart.isAfter(earliestDate)) {
                baselineStart
            } else {
                earliestDate
            }
            val previousLoads = dailyLoads.filter { load ->
                !load.date.isBefore(effectiveBaselineStart) && load.date.isBefore(windowStart)
            }
            val previousDayCount = ChronoUnit.DAYS.between(effectiveBaselineStart, windowStart).toFloat()
            val previousTriesPerDay = if (previousDayCount > 0f) {
                previousLoads.sumOf { it.triesLoad.toDouble() }.toFloat() / previousDayCount
            } else {
                0f
            }
            val windowDates = generateSequence(windowStart) { date ->
                val nextDate = date.plusDays(1)
                if (!nextDate.isAfter(endDate)) nextDate else null
            }.toList()
            val windowTriesLoad = windowDates.sumOf { date ->
                (dailyLoadByDate[date]?.triesLoad ?: 0f).toDouble()
            }.toFloat()
            val rollingLoadPercent = loadComponent(windowTriesLoad, previousTriesPerDay * 7f) * 100f

            if (previousTriesPerDay > 0f) {
                val x = ChronoUnit.DAYS.between(earliestDate, endDate).toFloat()
                Entry(x, rollingLoadPercent)
            } else {
                null
            }
        }
        .sortedBy { it.x }
        .toList()

    val rollingLoadDataSet = LineDataSet(rollingEntries, "7-day load %").apply {
        color = android.graphics.Color.YELLOW
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.YELLOW
        valueTextSize = 10f
    }
    val lineData = LineData(rollingLoadDataSet)
    lineData.setDrawValues(false)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = Color.CYAN
                data = CombinedData().apply {
                    setData(lineData)
                }
                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = Color.CYAN
                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val date = earliestDate.plusDays(value.toLong())
                        return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                    }
                }
            }
        },
        update = { chart ->
            chart.data = CombinedData().apply {
                setData(lineData)
            }
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    val date = earliestDate.plusDays(value.toLong())
                    return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                }
            }
            chart.notifyDataSetChanged()
            chart.invalidate()
        }
    )
}


data class GradeProgressionData(
    val earliestDate: LocalDate,
    val flashEntries: List<Entry>,
    val redpointEntries: List<Entry>,
    val projectEntries: List<Entry>
)

@RequiresApi(Build.VERSION_CODES.O)
fun calculateGradeProgressionData(itemList: List<Item>): GradeProgressionData {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val windowDays = 90L
    val climbItems = itemList
        .filter { it.type == 0 }
        .sortedBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
    val dates = climbItems
        .map { LocalDateTime.parse(it.name, formatter).toLocalDate() }
        .distinct()
        .sorted()
    val earliestDate = dates.firstOrNull() ?: LocalDate.now()

    fun gradeForProbability(windowItems: List<Item>, probability: Double): Float? {
        val priceFractions = windowItems.groupBy { it.price }.mapValues { (_, items) ->
            val sends = items.count { it.quantity > 0 }
            val attempts = items.count { it.quantity <= 0 }
            if (sends + attempts > 0) sends.toFloat() / (sends + attempts) else 0f
        }
        val xValues = priceFractions.keys.map { it.toFloat() }
        val yValues = priceFractions.values.toList()
        if (xValues.size < 2 || yValues.size < 2) {
            return null
        }

        return try {
            val parameters = LogisticFitter.fitLogistic(
                xValues.map { it.toDouble() }.toDoubleArray(),
                yValues.map { it.toDouble() }.toDoubleArray()
            ).toList()
            val a = parameters[0].toFloat()
            val b = parameters[1].toFloat()
            val c = parameters[2].toFloat()
            if (a <= probability.toFloat() || b == 0f) {
                null
            } else {
                val grade = (b * c - log(((a - probability) / probability), Math.exp(1.0))) / b
                grade.toFloat().takeIf { !it.isNaN() && !it.isInfinite() }
            }
        } catch (exception: Exception) {
            null
        }
    }

    val flashEntries = mutableListOf<Entry>()
    val redpointEntries = mutableListOf<Entry>()
    val projectEntries = mutableListOf<Entry>()

    dates.forEach { endDate ->
        val startDate = endDate.minusDays(windowDays - 1)
        val windowItems = climbItems.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(startDate) && !itemDate.isAfter(endDate)
        }
        val x = ChronoUnit.DAYS.between(earliestDate, endDate).toFloat()
        val flashGrade = gradeForProbability(windowItems, 0.5)
        val redpointGrade = gradeForProbability(windowItems, 0.206299)
        val projectGrade = gradeForProbability(windowItems, 0.0561257)

        if (flashGrade != null) {
            flashEntries.add(Entry(x, flashGrade))
        }
        if (redpointGrade != null) {
            redpointEntries.add(Entry(x, redpointGrade))
        }
        if (projectGrade != null) {
            projectEntries.add(Entry(x, projectGrade))
        }
    }

    return GradeProgressionData(
        earliestDate = earliestDate,
        flashEntries = flashEntries,
        redpointEntries = redpointEntries,
        projectEntries = projectEntries
    )
}

@Composable
fun ItemGradeProgressionChart(progressionData: GradeProgressionData, modifier: Modifier = Modifier) {
    val flashDataSet = LineDataSet(progressionData.flashEntries, "Flash").apply {
        color = Color.CYAN
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = Color.CYAN
        valueTextSize = 10f
    }
    val redpointDataSet = LineDataSet(progressionData.redpointEntries, "Redpoint").apply {
        color = Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = Color.MAGENTA
        valueTextSize = 10f
    }
    val projectDataSet = LineDataSet(progressionData.projectEntries, "Project").apply {
        color = android.graphics.Color.YELLOW
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.YELLOW
        valueTextSize = 10f
    }
    val lineData = LineData(flashDataSet, redpointDataSet, projectDataSet)
    lineData.setDrawValues(false)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = Color.CYAN
                data = CombinedData().apply {
                    setData(lineData)
                }
                description.isEnabled = false
                legend.textSize = 16f
                legend.textColor = Color.CYAN
                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val date = progressionData.earliestDate.plusDays(value.toLong())
                        return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                    }
                }
            }
        },
        update = { chart ->
            chart.data = CombinedData().apply {
                setData(lineData)
            }
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    val date = progressionData.earliestDate.plusDays(value.toLong())
                    return date.format(DateTimeFormatter.ofPattern("MM-dd"))
                }
            }
            chart.notifyDataSetChanged()
            chart.invalidate()
        }
    )
}


@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChart2(itemList: List<Item>, modifier: Modifier = Modifier, plotByWeek: Boolean) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val currentDate = LocalDate.now()

    // Filter items based on the desired time range
    /*val filteredItems = if (plotByWeek) {
        val oneYearAgo = currentDate.minusYears(1)
        itemList.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(oneYearAgo) && !itemDate.isAfter(currentDate)
        }
    } else {
        val threeMonthsAgo = currentDate.minusMonths(3)
        itemList.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(threeMonthsAgo) && !itemDate.isAfter(currentDate)
        }
    }*/

    val filteredItems = itemList
    // Group items by week or day
    val groupedQuantities = if (plotByWeek) {
        filteredItems.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).toLocalDate().get(WeekFields.of(Locale.getDefault()).weekOfYear()).toFloat()
        }
    } else {
        filteredItems.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
        }
    }

    val dailyQuantities = groupedQuantities.mapValues { (_, itemsForPeriod) ->
        val zeroQuantitySum = itemsForPeriod.filter { it.quantity > 0 }.sumOf { it.price.toInt() }
        val positiveQuantitySum = itemsForPeriod.filter { it.quantity == 0 }.sumOf { it.price.toInt() }
        listOf(zeroQuantitySum.toFloat(),zeroQuantitySum.toFloat()+ positiveQuantitySum.toFloat()) // maybe add a multiplier for no sends
    }

    val sends = dailyQuantities.values.map { it[0] }
    val trys = dailyQuantities.values.map { it[1] } - sends
    //Log.d("MyTag", mean(sends).toString())
    //Log.d("MyTag", variance(sends).toString())
    //Log.d("MyTag", mean(trys).toString())
    //Log.d("MyTag", variance(trys).toString())
    val count = dailyQuantities.size
    var minVariance = Float.MAX_VALUE

    val initialCoefficientA = 1.00f // Starting point of the search for 'a'
    val finalCoefficientA = 8.0f // Ending point of the search for 'a'
    val coefficientStep = 0.1f // Step size for 'a'

    val optimalCoefficientA = generateSequence(initialCoefficientA) { prev ->
        if (prev + coefficientStep <= finalCoefficientA) prev + coefficientStep else null
    }.minOfOrNull { currentCoefficientA ->
        val estimatedValues = sends.zip(trys).map { (send, tryi) ->
            send + tryi / currentCoefficientA
            }
        val variance = variance(estimatedValues)
        //Log.d("MyTag", variance.toString())
            variance
    } ?: initialCoefficientA // Handle case where range is empty

    val meanVPerDay = mean(sends.zip(trys).map { (send, tryi) ->
        send + tryi / optimalCoefficientA
    })

    val meanVDEntries = dailyQuantities.map { (day, _) ->
        Entry(day, meanVPerDay)
    }

    // Create BarEntry lists for each quantity category
    val zeroQuantityEntries = dailyQuantities.map { (day, sums) ->
        BarEntry(day, sums[0])
    }
    val positiveQuantityEntries = dailyQuantities.map { (day, sums) ->
        BarEntry(day, sums[1])
    }

    // Create BarDataSets with colors
    val zeroQuantityDataSet = BarDataSet(zeroQuantityEntries, "Send").apply {
        color = Color.CYAN
    }
    val positiveQuantityDataSet = BarDataSet(positiveQuantityEntries, "Attempt").apply {
        color = Color.MAGENTA
    }

    // Create BarData and configure stacking
    val barData = BarData(positiveQuantityDataSet, zeroQuantityDataSet)
    barData.isHighlightEnabled = false // Optional: disable highlighting
    barData.setDrawValues(false)      // Optional: hide values on bars

    val lineDataSet = LineDataSet(meanVDEntries, "Fit Curve").apply {
        color = android.graphics.Color.MAGENTA
        setDrawCircles(false)
        lineWidth = 2f
        valueTextColor = android.graphics.Color.MAGENTA
        valueTextSize = 12f
    }

    val lineData = LineData(lineDataSet)

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = android.graphics.Color.CYAN
                data = CombinedData().apply {
                    setData(barData)
                    setData(lineData)
                }
                description.isEnabled = false // Disable description
                legend.textSize = 16f
                legend.textColor = android.graphics.Color.CYAN

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return if (plotByWeek) {
                            "Week ${value.toInt()}"
                        } else {
                            val localDate = LocalDate.ofYearDay(LocalDate.now().year, value.toInt())
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            localDate.format(formatter)
                        }
                    }
                }
                //zoom(2f,1f, 0f,0f)
            }
        },
        update = { barChart ->
            barChart.data = CombinedData().apply {
                setData(barData)
                setData(lineData)
            }
            barChart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    return if (plotByWeek) {
                        "Week ${value.toInt()}"
                    } else {
                        val localDate = LocalDate.ofYearDay(LocalDate.now().year, value.toInt())
                        val formatter = DateTimeFormatter.ofPattern("MM-dd")
                        localDate.format(formatter)
                    }
                }
            }
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChart(
    itemList: List<Item>,
    modifier: Modifier = Modifier,
    plotByWeek: Boolean,
    showLoadOverlay: Boolean = false,
    baselineMonths: Int = 1,
    preparedData: VPointsChartModel
) {
    var defaultViewportKey by remember { mutableStateOf<String?>(null) }
    val chartKey =
        "vpoints-${preparedData.hashCode()}-${itemList.hashCode()}-$plotByWeek-$showLoadOverlay-$baselineMonths"
    val earliestDate = preparedData.earliestDate
    val barData = remember(preparedData) {
        val sentDataSet = BarDataSet(
            preparedData.sends.map { BarEntry(it.x, it.y) },
            "Send"
        ).apply { color = Color.CYAN }
        val attemptDataSet = BarDataSet(
            preparedData.attempts.map { BarEntry(it.x, it.y) },
            "Attempt"
        ).apply { color = Color.MAGENTA }
        BarData(attemptDataSet, sentDataSet).apply {
            isHighlightEnabled = false
            setDrawValues(false)
        }
    }
    val loadEntries = remember(itemList, earliestDate, plotByWeek, baselineMonths, showLoadOverlay) {
        if (showLoadOverlay) rollingLoadEntries(itemList, earliestDate, plotByWeek, baselineMonths) else emptyList()
    }
    val lineData = remember(loadEntries, showLoadOverlay) {
        if (showLoadOverlay) {
            val loadPercentDataSet = LineDataSet(
                loadEntries,
                "7-day load %"
            ).apply {
                color = android.graphics.Color.YELLOW
                axisDependency = YAxis.AxisDependency.RIGHT
                setDrawCircles(false)
                lineWidth = 2f
                valueTextColor = android.graphics.Color.YELLOW
                valueTextSize = 10f
            }
            LineData(loadPercentDataSet).apply { setDrawValues(false) }
        } else {
            null
        }
    }
    val combinedData = remember(barData, lineData) {
        CombinedData().apply {
            setData(barData)
            lineData?.let { setData(it) }
        }
    }
    val viewportKey = "${plotByWeek}-${barData.xMin}-${barData.xMax}"
    val defaultVisibleUnits = if (plotByWeek) 4f else 31f

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            CombinedChart(context).apply {
                xAxis.textSize = 16f
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = android.graphics.Color.CYAN
                axisRight.textSize = 16f
                axisRight.textColor = android.graphics.Color.YELLOW
                axisRight.axisMinimum = 0f
                axisRight.isEnabled = showLoadOverlay
                data = combinedData
                description.isEnabled = false // Disable description
                legend.textSize = 16f
                legend.textColor = android.graphics.Color.CYAN

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return if (plotByWeek) {
                            val weeksSinceEarliest = (value).toInt()
                            val date = earliestDate.plusDays(weeksSinceEarliest * 7L)
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            "${weeksSinceEarliest}"
                        } else {
                            val daysSinceEarliest = value.toInt()
                            val date = earliestDate.plusDays(daysSinceEarliest.toLong())
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            date.format(formatter)
                        }
                    }
                }

                //zoom(2f,1f, 0f,0f)
            }
        },
        update = { barChart ->
            if (barChart.tag == chartKey) return@AndroidView
            barChart.tag = chartKey
            barChart.data = combinedData
            barChart.axisRight.textSize = 16f
            barChart.axisRight.textColor = android.graphics.Color.YELLOW
            barChart.axisRight.axisMinimum = 0f
            barChart.axisRight.isEnabled = showLoadOverlay
            barChart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    return if (plotByWeek) {
                        val weeksSinceEarliest = (value).toInt()
                        "${weeksSinceEarliest}"
                    } else {
                        val daysSinceEarliest = value.toInt()
                        val date = earliestDate.plusDays(daysSinceEarliest.toLong())
                        val formatter = DateTimeFormatter.ofPattern("MM-dd")
                        date.format(formatter)
                    }
                }
            }
            barChart.notifyDataSetChanged()
            if (defaultViewportKey != viewportKey) {
                defaultViewportKey = viewportKey
                barChart.fitScreen()
                val xRange = barData.xMax - barData.xMin
                if (xRange > defaultVisibleUnits) {
                    barChart.zoom(xRange / defaultVisibleUnits, 1f, barData.xMax, 0f)
                    barChart.moveViewToX(barData.xMax)
                }
            }
            barChart.invalidate()
        }
    )
}
fun mean(data: List<Float>): Float {
    return data.sum() / data.size
}

fun variance(data: List<Float>): Float {
    val mean = mean(data)
    val vars = data.map { (it - mean).pow(2) }
    val variance = vars.sum() / (data.size - 1)
    return variance
}
@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChartHP(itemList: List<Item>, modifier: Modifier = Modifier, plotByWeek: Boolean) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val chartKey = "hp-${itemList.hashCode()}-$plotByWeek"
    val items = remember(itemList) {
        itemList.sortedBy {
            LocalDateTime.parse(it.name, formatter).toLocalDate()
        }
    }
    val earliestDate = items.minOfOrNull { item ->
        LocalDateTime.parse(item.name, formatter).toLocalDate()
    } ?: LocalDate.now()

    // Group items by day and calculate maximum values for each quantity category
    val groupedQuantities = remember(items, earliestDate, plotByWeek) {
        if (plotByWeek) {
            items.groupBy { item ->
                val localDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
                val daysSinceEarliest = ChronoUnit.DAYS.between(earliestDate, localDate)
                (daysSinceEarliest / 7.0f).toInt().toFloat()
            }
        } else {
            items.groupBy { item ->
                val localDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
                ChronoUnit.DAYS.between(earliestDate, localDate).toFloat()
            }
        }
    }

    val dailyQuantities = remember(groupedQuantities) {
        groupedQuantities.mapValues { (_, itemsForPeriod) ->
            val zeroQuantityMax = itemsForPeriod.filter { it.type == 0 }.maxOfOrNull { it.weight.toInt() * it.quantity }?.toFloat() ?: 0f
            val positiveQuantityMax = itemsForPeriod.filter { it.type == 1 }.maxOfOrNull { it.weight.toInt() * it.quantity }?.toFloat() ?: 0f
            listOf(zeroQuantityMax, positiveQuantityMax)
        }
    }

    // Create BarEntry lists for each quantity category
    val zeroQuantityEntries = dailyQuantities.map { (day, maxValues) ->
        BarEntry(day, maxValues[0])
    }
    val positiveQuantityEntries = dailyQuantities.map { (day, maxValues) ->
        BarEntry(day, maxValues[1])
    }

    // Create BarDataSets with colors
    val zeroQuantityDataSet = BarDataSet(zeroQuantityEntries, "Pulls").apply {
        color = Color.CYAN
    }
    val positiveQuantityDataSet = BarDataSet(positiveQuantityEntries, "Hangs").apply {
        color = Color.MAGENTA
    }

    // Create BarData and configure stacking
    val barData = BarData(positiveQuantityDataSet, zeroQuantityDataSet)
    barData.isHighlightEnabled = false // Optional: disable highlighting
    barData.setDrawValues(false)      // Optional: hide values on bars

    // ... rest of your Composable code (AndroidView, configuration, etc.)
    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            BarChart(context).apply {
                // Configure chart appearance (axis labels, grid, etc.)
                xAxis.textSize = 16f
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                axisLeft.textColor = android.graphics.Color.CYAN

                data = barData
                description.isEnabled = false // Disable description
                legend.textSize = 16f
                legend.textColor = android.graphics.Color.CYAN

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return if (plotByWeek) {
                            "${value.toInt()}" // Display week number
                        } else {
                            val localDate = earliestDate.plusDays(value.toLong())
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            localDate.format(formatter)
                        }
                    }
                }
            }
        },
        update = { barChart ->
            if (barChart.tag == chartKey) return@AndroidView
            barChart.tag = chartKey
            barChart.data = barData
            barChart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float): String {
                    return if (plotByWeek) {
                        "${value.toInt()}"
                    } else {
                        val localDate = earliestDate.plusDays(value.toLong())
                        val formatter = DateTimeFormatter.ofPattern("MM-dd")
                        localDate.format(formatter)
                    }
                }
            }
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}


@Preview(showBackground = true)
@Composable
fun HomeBodyPreview() {
    InventoryTheme {
        HomeBody(
            itemList = listOf(
                //Item(1, "Game", 10, 20), Item(2, "Pen", 200.0, 30), Item(3, "TV", 300.0, 50)
            ),
            eventList = listOf(),
            onItemClick = {},
            onEventClick = {},
            onEventSave = {},
            calculateStatistics = { _, _ -> List(11) { 0f } },
            prepareVPointsChart = { _, _ -> VPointsChartModel(LocalDate.now(), emptyList(), emptyList()) }
        )
    }
}

@Preview(showBackground = true)
@Composable
fun HomeBodyEmptyListPreview() {
    InventoryTheme {
        HomeBody(
            itemList = listOf(),
            eventList = listOf(),
            onItemClick = {},
            onEventClick = {},
            onEventSave = {},
            calculateStatistics = { _, _ -> List(11) { 0f } },
            prepareVPointsChart = { _, _ -> VPointsChartModel(LocalDate.now(), emptyList(), emptyList()) }
        )
    }
}

@RequiresApi(Build.VERSION_CODES.O)
@Preview(showBackground = true)
@Composable
fun InventoryItemPreview() {
    InventoryTheme {
        InventoryItem(
            Item(1, "Game", 10, 20,1,1.0,1,5,0,0),
        )
    }
}

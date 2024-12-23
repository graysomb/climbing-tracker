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
import android.widget.Toast
import androidx.annotation.RequiresApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.room.Room
import androidx.room.RoomDatabase
import com.example.inventory.InventoryTopAppBar
import com.example.inventory.R
import com.example.inventory.data.Item
import com.example.inventory.ui.AppViewModelProvider
import com.example.inventory.ui.navigation.NavigationDestination
import com.example.inventory.ui.theme.InventoryTheme
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.formatter.ValueFormatter
import com.opencsv.CSVWriter
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
import kotlin.concurrent.read
import kotlin.math.round


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
    modifier: Modifier = Modifier,
    viewModel: HomeViewModel = viewModel(factory = AppViewModelProvider.Factory)
) {
    val homeUiState by viewModel.homeUiState.collectAsState()
    val scrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior()
    val currentTime by viewModel.currentTime.collectAsState()

    Scaffold(
        modifier = modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        topBar = {
            InventoryTopAppBar(
                title = TimeDifference.getFormattedDuration(currentTime, homeUiState.lastItem.name) ,
                //title = currentTime,
                canNavigateBack = false,
                scrollBehavior = scrollBehavior
            )
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
            onItemClick = navigateToItemUpdate,
            modifier = modifier
                .padding(innerPadding)
                .fillMaxSize()
        )
    }
}

@Composable
private fun HomeBody(
    itemList: List<Item>, onItemClick: (Int) -> Unit, modifier: Modifier = Modifier
) {
    var chartType by remember { mutableStateOf(true) }
    var plotByWeek by remember { mutableStateOf(false) }


    fun writeItemsToCsv(context: Context, items: List<Item>) {
        val resolver = context.contentResolver
        val contentValues = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, "climb_data.csv")
            put(MediaStore.MediaColumns.MIME_TYPE, "text/csv")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        }

        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)

        uri?.let {
            resolver.openOutputStream(it)?.use { outputStream ->
                OutputStreamWriter(outputStream).use { writer ->
                    val csvWriter = CSVWriter(writer)
                    val header = arrayOf("id", "time", "grade", "send/reps", "type", "weight")
                    csvWriter.writeNext(header)

                    items.forEach { item ->
                        val row = arrayOf(item.id.toString(), item.name, item.price.toString(), item.quantity.toString(), item.type.toString(), item.weight.toString())
                        csvWriter.writeNext(row)
                    }

                    csvWriter.close()
                }
            }
        }
    }
    val context = LocalContext.current

    fun backupDatabaseToDownloads(context: Context) {
        val dbFile = context.getDatabasePath("item_database")

        val resolver = context.contentResolver
        val contentValues = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, "my_database_backup.db")
            put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        }

        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)

        uri?.let {
            resolver.openOutputStream(it)?.use { outputStream ->
                dbFile.inputStream().use { inputStream ->
                    inputStream.copyTo(outputStream)
                }
            }
        }
    }

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
            Button(onClick = { chartType = !chartType }) {
                if (chartType) {
                    Text(text = "V Points")
                } else {
                    Text(text = "LBS")
                }
            }
            Button(onClick = { plotByWeek = !plotByWeek }) {
                if (plotByWeek) {
                    Text(text = "Week")
                } else {
                    Text(text = "Day")
                }
            }
            Button(onClick = { writeItemsToCsv(context, itemList) }) {
                Text(text = "Export")
            }
            Button(onClick = { backupDatabaseToDownloads( context) }) {
                Text(text = "Backup")
            }
        }
            if (chartType) {
                ItemBarChart(itemList, Modifier.weight(1f), plotByWeek)
            }else {
                ItemBarChartHP(itemList, Modifier.weight(1f), plotByWeek)
            }
            InventoryList(
                itemList = itemList,
                onItemClick = { onItemClick(it.id) },
                modifier = Modifier.padding(horizontal = dimensionResource(id = R.dimen.padding_small))
            )
        }
    }
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
fun ItemBarChart2(itemList: List<Item>, modifier: Modifier = Modifier) {


    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME

    val items = itemList

    val dailyQuantities = items.groupBy { item ->
        LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
    }.mapValues { (_, itemsForDay) ->
        itemsForDay.sumOf { it.price.toInt() }
    }

    val entries = dailyQuantities.map { (day, sumday) ->
        BarEntry(day, sumday.toFloat())
    }

    val dataSet = BarDataSet(entries, "Item Quantities").apply {
        // Customize appearance (color, etc.)
    }

    val barData = BarData(dataSet)
    barData.setDrawValues(false)
    Text(text = "V Points", style = MaterialTheme.typography.titleMedium)
    AndroidView(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(.3f),
        factory = { context ->
            BarChart(context).apply {
                // Configure chart appearance (axis labels, grid, etc.)
                xAxis.textSize = 16f
                //xAxis.textColor = MaterialTheme.colorScheme.primary.toArgb()
                xAxis.textColor = android.graphics.Color.CYAN
                xAxis.position = com.github.mikephil.charting.components.XAxis.XAxisPosition.BOTTOM
                axisLeft.textSize = 16f
                //xAxis.textColor = MaterialTheme.colorScheme.primary.toArgb()
                axisLeft.textColor = android.graphics.Color.CYAN

                data = barData
                description.isEnabled = false // Disable description
                legend.isEnabled = false // Disable legend
                // ... other configurations

                xAxis.valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        val localDate = LocalDate.ofYearDay(LocalDate.now().year, value.toInt())
                        val formatter = DateTimeFormatter.ofPattern("MM-dd")
                        return localDate.format(formatter)
                    }
                }


            }
        },
        update = { barChart ->
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}


@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChart(itemList: List<Item>, modifier: Modifier = Modifier, plotByWeek: Boolean) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val currentDate = LocalDate.now()

    // Filter items based on the desired time range
    val filteredItems = if (plotByWeek) {
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
    }

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
        val positiveQuantitySum = itemsForPeriod.filter { it.quantity > -1 }.sumOf { it.price.toInt() }
        listOf(zeroQuantitySum.toFloat(), positiveQuantitySum.toFloat())
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

    AndroidView(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(.3f),
        factory = { context ->
            BarChart(context).apply {
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
                            "Week ${value.toInt()}"
                        } else {
                            val localDate = LocalDate.ofYearDay(LocalDate.now().year, value.toInt())
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            localDate.format(formatter)
                        }
                    }
                }
            }
        },
        update = { barChart ->
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}

@RequiresApi(Build.VERSION_CODES.O)
@Composable
fun ItemBarChartHP(itemList: List<Item>, modifier: Modifier = Modifier, plotByWeek: Boolean) {
    val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
    val items = itemList

    // Group items by day and calculate maximum values for each quantity category
    val groupedQuantities = if (plotByWeek) {
        items.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).toLocalDate().get(WeekFields.of(Locale.getDefault()).weekOfYear()).toFloat()
        }
    } else {
        items.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
        }
    }

    val dailyQuantities = groupedQuantities.mapValues { (_, itemsForPeriod) ->
        val zeroQuantityMax = itemsForPeriod.filter { it.type == 0 }.maxOfOrNull { it.weight.toInt() * it.quantity }?.toFloat() ?: 0f
        val positiveQuantityMax = itemsForPeriod.filter { it.type == 1 }.maxOfOrNull { it.weight.toInt() * it.quantity }?.toFloat() ?: 0f
        listOf(zeroQuantityMax, positiveQuantityMax)
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
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(.3f),
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
                            val localDate = LocalDate.ofYearDay(LocalDate.now().year, value.toInt())
                            val formatter = DateTimeFormatter.ofPattern("MM-dd")
                            localDate.format(formatter)
                        }
                    }
                }
            }
        },
        update = { barChart ->
            barChart.notifyDataSetChanged()
            barChart.invalidate()
        }
    )
}


@Preview(showBackground = true)
@Composable
fun HomeBodyPreview() {
    InventoryTheme {
        HomeBody(listOf(
            //Item(1, "Game", 10, 20), Item(2, "Pen", 200.0, 30), Item(3, "TV", 300.0, 50)
        ), onItemClick = {})
    }
}

@Preview(showBackground = true)
@Composable
fun HomeBodyEmptyListPreview() {
    InventoryTheme {
        HomeBody(listOf(), onItemClick = {})
    }
}

@RequiresApi(Build.VERSION_CODES.O)
@Preview(showBackground = true)
@Composable
fun InventoryItemPreview() {
    InventoryTheme {
        InventoryItem(
            Item(1, "Game", 10, 20,1,1.0,1),
        )
    }
}

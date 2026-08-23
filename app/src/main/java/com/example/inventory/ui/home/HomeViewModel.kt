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

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.inventory.data.Event
import com.example.inventory.data.Item
import com.example.inventory.data.ItemsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/**
 * ViewModel to retrieve all items in the Room database.
 */
class HomeViewModel(private val itemsRepository: ItemsRepository) : ViewModel() {
    private val calculationCache = LinkedHashMap<String, List<Float>>()
    private val vPointsChartCache = LinkedHashMap<String, VPointsChartModel>()
    private val acwrChartCache = LinkedHashMap<String, AcwrChartModel>()

    /**
     * Holds home ui state. The list of items are retrieved from [ItemsRepository] and mapped to
     * [HomeUiState]
     */
    private val _currentTime = MutableStateFlow("")
    val currentTime: StateFlow<String> = _currentTime.asStateFlow()

    init {
        viewModelScope.launch {
            timeTickFlow().collect {
                _currentTime.value = it
            }
        }
    }

    val homeUiState: StateFlow<HomeUiState> =
        combine(
            itemsRepository.getAllItemsStream(),
            itemsRepository.getLastItemStream(),
            itemsRepository.getAllEventsStream()
        ) { allItems, lastItem, allEvents ->
            HomeUiState(
                itemList = allItems,
                eventList = allEvents,
                lastItem = lastItem ?: Item(1, LocalDateTime.now().toString(), 0, 0, 0, 0.0, 0, 5, 0, 0)
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(TIMEOUT_MILLIS),
            initialValue = HomeUiState(lastItem = Item(1, LocalDateTime.now().toString(), 0, 0, 0, 0.0, 0, 5, 0, 0))
        )

    fun addEvent(event: Event) {
        viewModelScope.launch {
            itemsRepository.insertEvent(event)
        }
    }

    suspend fun getHomeCalculations(itemList: List<Item>, baselineMonths: Int): List<Float> =
        withContext(Dispatchers.Default) {
            val cacheKey = "${itemList.hashCode()}-${itemList.size}-$baselineMonths"
            synchronized(calculationCache) { calculationCache[cacheKey] }?.let { return@withContext it }

            val calculated = calculateHomeCalcs(itemList, baselineMonths)
            synchronized(calculationCache) {
                if (calculationCache.size >= MAX_CACHE_ENTRIES) calculationCache.clear()
                calculationCache[cacheKey] = calculated
            }
            calculated
        }

    suspend fun getVPointsChartModel(itemList: List<Item>, plotByWeek: Boolean): VPointsChartModel =
        withContext(Dispatchers.Default) {
            val cacheKey = "${itemList.hashCode()}-${itemList.size}-$plotByWeek"
            synchronized(vPointsChartCache) { vPointsChartCache[cacheKey] }?.let { return@withContext it }

            val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
            val datedItems = itemList
                .map { item -> item to LocalDateTime.parse(item.name, formatter).toLocalDate() }
                .sortedBy { (_, date) -> date }
            val earliestDate = datedItems.firstOrNull()?.second ?: LocalDate.now()
            val groupedItems = datedItems.groupBy { (_, date) ->
                val daysSinceEarliest = ChronoUnit.DAYS.between(earliestDate, date).toFloat()
                if (plotByWeek) (daysSinceEarliest / 7f).toInt().toFloat() else daysSinceEarliest
            }
            val sends = ArrayList<ChartPoint>(groupedItems.size)
            val attempts = ArrayList<ChartPoint>(groupedItems.size)
            groupedItems.forEach { (x, entries) ->
                val itemsForPeriod = entries.map { it.first }
                val sentVPoints = itemsForPeriod.filter { it.quantity > 0 }.sumOf { it.price }.toFloat()
                val attemptedVPoints = sentVPoints +
                    itemsForPeriod.filter { it.quantity == 0 }.sumOf { it.price }.toFloat()
                sends.add(ChartPoint(x, sentVPoints))
                attempts.add(ChartPoint(x, attemptedVPoints))
            }
            val model = VPointsChartModel(earliestDate, sends, attempts)
            synchronized(vPointsChartCache) {
                if (vPointsChartCache.size >= MAX_CACHE_ENTRIES) vPointsChartCache.clear()
                vPointsChartCache[cacheKey] = model
            }
            model
        }

    suspend fun getAcwrChartModel(itemList: List<Item>, eventList: List<Event>): AcwrChartModel =
        withContext(Dispatchers.Default) {
            val cacheKey = "${itemList.hashCode()}-${eventList.hashCode()}"
            synchronized(acwrChartCache) { acwrChartCache[cacheKey] }?.let { return@withContext it }

            val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
            val climbsByDate = itemList
                .asSequence()
                .filter { it.type == 0 }
                .groupBy { LocalDateTime.parse(it.name, formatter).toLocalDate() }
            val injuryDates = eventList
                .asSequence()
                .filter { it.type == 0 }
                .map { LocalDateTime.parse(it.time, formatter).toLocalDate() }
                .distinct()
                .sorted()
                .toList()
            val earliestDate = (climbsByDate.keys + injuryDates).minOrNull() ?: LocalDate.now()
            val latestRecordedDate = (climbsByDate.keys + injuryDates).maxOrNull() ?: earliestDate
            val latestDate = if (latestRecordedDate.isAfter(LocalDate.now())) latestRecordedDate else LocalDate.now()
            val dayCount = ChronoUnit.DAYS.between(earliestDate, latestDate).toInt() + 1
            val totalPrefix = FloatArray(dayCount + 1)
            val meanPrefix = FloatArray(dayCount + 1)

            for (dayIndex in 0 until dayCount) {
                val date = earliestDate.plusDays(dayIndex.toLong())
                val climbsForDay = climbsByDate[date].orEmpty()
                val totalVPoints = climbsForDay.sumOf { it.price }.toFloat()
                val meanVGrade = if (climbsForDay.isNotEmpty()) {
                    totalVPoints / climbsForDay.size.toFloat()
                } else 0f
                totalPrefix[dayIndex + 1] = totalPrefix[dayIndex] + totalVPoints
                meanPrefix[dayIndex + 1] = meanPrefix[dayIndex] + meanVGrade
            }

            fun windowSum(prefix: FloatArray, endIndex: Int, windowDays: Int): Float {
                val startIndex = (endIndex - windowDays + 1).coerceAtLeast(0)
                return prefix[endIndex + 1] - prefix[startIndex]
            }

            val meanVAcwr = ArrayList<ChartPoint>(dayCount)
            val totalVAcwr = ArrayList<ChartPoint>(dayCount)
            for (dayIndex in 0 until dayCount) {
                val acuteTotal = windowSum(totalPrefix, dayIndex, 7)
                val chronicTotal = windowSum(totalPrefix, dayIndex, 28)
                val acuteMean = windowSum(meanPrefix, dayIndex, 7) / 7f
                val chronicMean = windowSum(meanPrefix, dayIndex, 28) / 28f
                val totalAcwr = if (chronicTotal > 0f) acuteTotal / chronicTotal else 0f
                val meanAcwr = if (chronicMean > 0f) acuteMean / chronicMean else 0f
                totalVAcwr.add(
                    ChartPoint(dayIndex.toFloat(), totalAcwr / INJURY_TOTAL_ACWR_MEAN * 100f)
                )
                meanVAcwr.add(
                    ChartPoint(dayIndex.toFloat(), meanAcwr / INJURY_MEAN_ACWR_MEAN * 100f)
                )
            }
            val injuries = injuryDates.map { injuryDate ->
                val dayIndex = ChronoUnit.DAYS.between(earliestDate, injuryDate).toInt()
                val markerHeight = maxOf(
                    meanVAcwr.getOrNull(dayIndex)?.y ?: 0f,
                    totalVAcwr.getOrNull(dayIndex)?.y ?: 0f,
                    0.05f
                )
                ChartPoint(dayIndex.toFloat(), markerHeight)
            }
            val model = AcwrChartModel(earliestDate, meanVAcwr, totalVAcwr, injuries)
            synchronized(acwrChartCache) {
                if (acwrChartCache.size >= MAX_CACHE_ENTRIES) acwrChartCache.clear()
                acwrChartCache[cacheKey] = model
            }
            model
        }

    fun timeTickFlow(): Flow<String> = flow {
        while (true) {
            val currentDateTime = LocalDateTime.now()
            //val lastItem = homeUiState.value.lastItem
            //val deformatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
            //val lastTime = LocalDateTime.parse(lastItem?.name,deformatter)
            //val timeDifference = Duration.between(lastTime, currentDateTime)
            val formattedTime = currentDateTime.format(DateTimeFormatter.ofPattern("HH:mm:ss"))
            emit(formattedTime)
            delay(1000) // Update every second
        }
    }
    companion object {
        private const val TIMEOUT_MILLIS = 5_000L
        private const val MAX_CACHE_ENTRIES = 24
        private const val INJURY_TOTAL_ACWR_MEAN = 0.5084f
        private const val INJURY_MEAN_ACWR_MEAN = 1.9742f
    }
}

data class ChartPoint(val x: Float, val y: Float)

data class VPointsChartModel(
    val earliestDate: LocalDate,
    val sends: List<ChartPoint>,
    val attempts: List<ChartPoint>
)

data class AcwrChartModel(
    val earliestDate: LocalDate,
    val meanVAcwr: List<ChartPoint>,
    val totalVAcwr: List<ChartPoint>,
    val injuries: List<ChartPoint>
)

/**
 * Ui State for HomeScreen
 */
data class HomeUiState(
    val itemList: List<Item> = listOf(),
    val eventList: List<Event> = listOf(),
    val lastItem: Item
)

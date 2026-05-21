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
import com.example.inventory.data.Item
import com.example.inventory.data.ItemsRepository
import com.github.mikephil.charting.data.Entry
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.launch
import org.apache.commons.math3.analysis.function.Log
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.WeekFields
import java.util.Locale
import kotlin.math.log

/**
 * ViewModel to retrieve all items in the Room database.
 */
class HomeViewModel(itemsRepository: ItemsRepository) : ViewModel() {

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
            itemsRepository.getLastItemStream()
        ) { allItems, lastItem ->
            HomeUiState(
                itemList = allItems,
                lastItem = lastItem ?: Item(1, LocalDateTime.now().toString(), 0, 0, 0, 0.0, 0, 5, 0, 0),
                calcs = performCalculations(allItems)
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(TIMEOUT_MILLIS),
            initialValue = HomeUiState(lastItem = Item(1, LocalDateTime.now().toString(), 0, 0, 0, 0.0, 0, 5, 0, 0))
        )

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
    private fun performCalculations(itemList: List<Item>): List<Float> {

        val formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME
        val currentDate = LocalDate.now()
        val oneMonthsAgo = currentDate.minusMonths(3)

        val filteredItems = itemList.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(oneMonthsAgo) && !itemDate.isAfter(currentDate)
        }

        //val filteredItems = itemList

        // Group items by week or day
        val groupedQuantities = filteredItems.groupBy { item ->
            LocalDateTime.parse(item.name, formatter).dayOfYear.toFloat()
        }


        val dailyQuantities = groupedQuantities.mapValues { (_, itemsForPeriod) ->
            val zeroQuantitySum = itemsForPeriod.filter { it.quantity > 0 }.sumOf { it.price.toInt() }
            val positiveQuantitySum = itemsForPeriod.filter { it.quantity == 0 }.sumOf { it.price.toInt() }
            listOf(zeroQuantitySum.toFloat(),zeroQuantitySum.toFloat()+ positiveQuantitySum.toFloat()) // maybe add a multiplier for no sends
        }

        val sends = dailyQuantities.values.map { it[0] }
        val trys = dailyQuantities.values.map { it[1] }
        val trysF = trys.filter { it != 0f }
        val sendsF = sends.filter { it != 0f }
        val sendsPerDay = if (sendsF.isNotEmpty()) sendsF.average().toFloat() else 0f
        val triesPerDay = if (trysF.isNotEmpty()) trysF.average().toFloat() else 0f

        fun loadingComponent(currentLoad: Float, baselineLoad: Float): Float {
            return if (baselineLoad > 0f) currentLoad / baselineLoad else 0f
        }

        fun loadForItems(items: List<Item>): List<Float> {
            val sendsLoad = items.filter { it.quantity > 0 }.sumOf { it.price.toInt() }.toFloat()
            val triesLoad = sendsLoad + items.filter { it.quantity == 0 }.sumOf { it.price.toInt() }.toFloat()
            return listOf(sendsLoad, triesLoad)
        }

        val todayItems = filteredItems.filter { item ->
            LocalDateTime.parse(item.name, formatter).toLocalDate() == currentDate
        }
        val lastSevenDays = currentDate.minusDays(6)
        val lastSevenDayItems = filteredItems.filter { item ->
            val itemDate = LocalDateTime.parse(item.name, formatter).toLocalDate()
            !itemDate.isBefore(lastSevenDays) && !itemDate.isAfter(currentDate)
        }
        val todayLoad = loadForItems(todayItems)
        val weekLoad = loadForItems(lastSevenDayItems)
        val loadingThisDay = (
            loadingComponent(todayLoad[0], sendsPerDay) +
                loadingComponent(todayLoad[1], triesPerDay)
            ) * 0.5f * 100f
        val loadingThisWeek = (
            loadingComponent(weekLoad[0], sendsPerDay * 7f) +
                loadingComponent(weekLoad[1], triesPerDay * 7f)
            ) * 0.5f * 100f

        val groupedByPrice = filteredItems.groupBy { it.price }

        val priceFractions = groupedByPrice.mapValues { (_, items) ->
            val sends = items.count { it.quantity > 0 }
            val sendsV = items.filter{ it.quantity > 0 }.sumOf{it.price.toInt()}
            val attempts = items.count { it.quantity <= 0 }
            if (sends + attempts > 0) sends.toFloat() / (sends + attempts) else 0f
            }

        // Fit the data to c / (exp((x - a) / b) + 1) using least squares
        val xValues = priceFractions.keys.map { it.toFloat() }
        val yValues = priceFractions.values.toList()
        val fitEntries = mutableListOf<Entry>()

         val paramsFit = if (xValues.isNotEmpty() && yValues.isNotEmpty() ) {
            val initialA = xValues.average().toFloat()
            val initialB = (xValues.maxOrNull()!! - xValues.minOrNull()!!) / 8
            val initialC = yValues.maxOrNull() ?: 1f

            // Convert Kotlin collections to Java arrays
            val xValuesJava = xValues.map { it.toDouble() }.toDoubleArray()
            val yValuesJava = yValues.map { it.toDouble() }.toDoubleArray()

            // Perform least squares fitting using the Java class LogisticFitter
            val parameters = LogisticFitter.fitLogistic(xValuesJava, yValuesJava)
            parameters.toList()
            } else {
                listOf(0f, 0f, 0f)
         }
        val a = paramsFit[0].toFloat()
        val b  = paramsFit[1].toFloat()
        val c = paramsFit[2].toFloat()
        val send50 = (b*c - log((-1 + 2*a).toDouble(), Math.exp(1.0).toDouble()))/b
        val p3 = 0.206299
        val send3try = (b*c - log(((a-p3)/p3).toDouble(), Math.exp(1.0).toDouble()))/b
        val p6 = 0.109101
        val p12 = 0.0561257
        val send6try = (b*c - log(((a-p12)/p12).toDouble(), Math.exp(1.0).toDouble()))/b

        return listOf(
            triesPerDay,
            sendsPerDay,
            send50.toFloat(),
            send3try.toFloat(),
            send6try.toFloat(),
            loadingThisDay,
            loadingThisWeek
        )
    }

    companion object {
        private const val TIMEOUT_MILLIS = 5_000L
    }
}

/**
 * Ui State for HomeScreen
 */
data class HomeUiState(val itemList: List<Item> = listOf(),val lastItem: Item, val calcs: List<Float> = listOf())

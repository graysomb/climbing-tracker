package com.example.inventory.ui.home;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public class TimeDifference {

    public static String getFormattedDuration(String currentTime, String lastTime) {
        DateTimeFormatter deformatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME;
        DateTimeFormatter reformatter = DateTimeFormatter.ofPattern("HH:mm:ss");

        LocalDateTime lastDateTime = LocalDateTime.parse(lastTime, deformatter);
        //LocalDateTime currentTimeOnly  = LocalDateTime.parse(currentTime, reformatter);

        //LocalDate currentDate = LocalDate.now();
        //LocalDateTime currentDateTime = LocalDateTime.of(currentDate, currentTimeOnly);

        Duration duration = Duration.between(lastDateTime, LocalDateTime.now());

        long seconds = duration.getSeconds();
        long absSeconds = Math.abs(seconds);
        String positiveDuration = String.format("%02d:%02d", absSeconds / 60, absSeconds % 60);

        return seconds < 0 ? "-" + positiveDuration : positiveDuration;
    }
}

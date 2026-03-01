#!/bin/bash

version="V0.4"
NAME=$(basename "$0")

PWMDEV="0000:00:17.0"
PWMNUM=`ls -al /sys/class/pwm/ | grep "$PWMDEV" | awk '{ print $9}'`
SYSPATH="/sys/class/pwm/$PWMNUM"

usage() {
  echo "$version"
  echo "Usage:
  $NAME <command> [options]

Options:
  -h, --help    Show usage

Init motor and servo power and duty cycle:
  sudo ./pwm.sh enable

Disable motor and servo power
  sudo ./pwm.sh disable

Motor control Commands:
  sudo ./pwm.sh motor fw            //Forward
  sudo ./pwm.sh motor fw slow       //Slow Forward
  sudo ./pwm.sh motor fw max        //Max Forward
  sudo ./pwm.sh motor stop          //Stop 
  sudo ./pwm.sh motor bw            //Backward
  sudo ./pwm.sh motor bw slow        //Slow Backward
  sudo ./pwm.sh motor bw max        //Max Backward
  sudo ./pwm.sh motor [duty_cycle]  //Custom motor duty cycle

Servo control Commands:
  sudo ./pwm.sh servo left            //Turn Left
  sudo ./pwm.sh servo mid             //Middle 
  sudo ./pwm.sh servo right           //Turn Right
  sudo ./pwm.sh servo [duty_cycle]    //Custom ESC duty cycle

LED PWM Control:
   sudo ./pwm.sh led off      //Turn off all LED
   sudo ./pwm.sh led on       //Turn on all LED
   sudo ./pwm.sh led r        //Turn on all LED to RED
   sudo ./pwm.sh led g        //Turn on all LED to Green
   sudo ./pwm.sh led b        //Turn on all LED to Blue
"
}

export_pwm() {
  pwm_num=$1
  pwm_path="$SYSPATH/pwm$pwm_num"

  if [ ! -d $pwm_path ]; then
    echo $pwm_num > $SYSPATH/export
  fi

}

unexport_pwm() {
  pwm_num=$1
  pwm="$SYSPATH/pwm$pwm_num"

  if [ -d $pwm ]; then
     echo $pwm_num > $SYSPATH/unexport
  fi
}

unexport_pwm_dev() {
  echo "Unexport PWM Device Tree"
  unexport_pwm 0
  unexport_pwm 1
  unexport_pwm 2
  unexport_pwm 3
  unexport_pwm 4
}

export_gpio() {
  pin_num=$1
  pin_dir=$2
  pin_val=$3
  gpio_path="/sys/class/gpio/gpio$pin_num"

  if [ ! -d $gpio_path ]; then
    echo $pin_num > /sys/class/gpio/export
  fi
  if [ "$pin_dir" ]; then
    echo $pin_dir > $gpio_path/direction
  fi
  if [ "$pin_dir" = "out" ]; then
    if [ "$pin_val" ]; then
      echo $pin_val > $gpio_path/value
    fi
  fi

  chmod 666 $gpio_path/value
}

pwm_enable() {
  export_gpio 514 out 0 
  
}

pwm_disable() {
  export_gpio 514 out 1 
  
}


motor_crtl() {
  echo "Motor control"
  # Motor control
  export_pwm 0
  echo 20000000 > $SYSPATH/pwm0/period

  case "$1" in
  fw)
    if [ "$2" == "slow" ]; then
      echo "Slow Forward"
      echo 1400000 > $SYSPATH/pwm0/duty_cycle
    elif [ "$2" == "max" ]; then
      echo "Max Forward"
      echo 1200000 > $SYSPATH/pwm0/duty_cycle
    else
      echo "Normal Forward"
      echo 1350000 > $SYSPATH/pwm0/duty_cycle
    fi
  ;;
  stop)
    echo "Stop"
    echo 1450000 > $SYSPATH/pwm0/duty_cycle
  ;;
  bw)
    if [ "$2" == "slow" ]; then
      echo "slow Backward"
      echo 1500000 > $SYSPATH/pwm0/duty_cycle
    elif [ "$2" == "max" ]; then
      echo "Max Backward"
      echo 1700000 > $SYSPATH/pwm0/duty_cycle
    else
      echo "Normal Backward"
      echo 1550000 > $SYSPATH/pwm0/duty_cycle
    fi
  ;;
  *)
    #echo "custom servo duty cycle $1"
    echo $1 > $SYSPATH/pwm0/duty_cycle
    ;;
  esac

  duty=`cat $SYSPATH/pwm0/duty_cycle`

  echo "Motor duty cycle : $duty"
}

servo_crtl() {
  echo "Servo control"
  # Servo control
  export_pwm 1
  echo 20000000 > $SYSPATH/pwm1/period

  case "$1" in
  left)
  echo "Turn Left"
    echo 1700000 > $SYSPATH/pwm1/duty_cycle
  ;;
  mid)
  echo "Middle"
    echo 1450000 > $SYSPATH/pwm1/duty_cycle
  ;;
  right)
  echo "Turn Right"
    echo 1200000 > $SYSPATH/pwm1/duty_cycle
  ;;
  *)
    #echo "custom esc duty cycle $1"
    echo $1 > $SYSPATH/pwm1/duty_cycle
    ;;
  esac
  duty=`cat $SYSPATH/pwm1/duty_cycle`

  echo "Servo duty cycle : $duty"
}

led_pwm_ctrl() {
  echo "LED PWM control"
  # LED PWM control

  
  case "$1" in
  on)
  echo "Turn On LED"
    #LED R
    export_pwm 2
    echo 20000000 > $SYSPATH/pwm2/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm2/duty_cycle 

    #LED G
    export_pwm 3 
    echo 20000000 > $SYSPATH/pwm3/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm3/duty_cycle 

    #LED B
    export_pwm 4 
    echo 20000000 > $SYSPATH/pwm4/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm4/duty_cycle 
  ;;
  off)
  echo "Turn off LED"
    #LED R
    export_pwm 2
    echo 20000000 > $SYSPATH/pwm2/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm2/duty_cycle 

    #LED G
    export_pwm 3 
    echo 20000000 > $SYSPATH/pwm3/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm3/duty_cycle 

    #LED B
    export_pwm 4 
    echo 20000000 > $SYSPATH/pwm4/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm4/duty_cycle 
  ;;
  r)
    #LED R
    export_pwm 2
    echo 20000000 > $SYSPATH/pwm2/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm2/duty_cycle 

    #LED G
    export_pwm 3 
    echo 20000000 > $SYSPATH/pwm3/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm3/duty_cycle 

    #LED B
    export_pwm 4 
    echo 20000000 > $SYSPATH/pwm4/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm4/duty_cycle 
  ;;
  g)
    #LED R
    export_pwm 2
    echo 20000000 > $SYSPATH/pwm2/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm2/duty_cycle 

    #LED G
    export_pwm 3 
    echo 20000000 > $SYSPATH/pwm3/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm3/duty_cycle 

    #LED B
    export_pwm 4 
    echo 20000000 > $SYSPATH/pwm4/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm4/duty_cycle 
  ;;
  b)
    #LED R
    export_pwm 2
    echo 20000000 > $SYSPATH/pwm2/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm2/duty_cycle 

    #LED G
    export_pwm 3 
    echo 20000000 > $SYSPATH/pwm3/period

    #range 0 ~ 20000000
    echo 0 > $SYSPATH/pwm3/duty_cycle 

    #LED B
    export_pwm 4 
    echo 20000000 > $SYSPATH/pwm4/period

    #range 0 ~ 20000000
    echo 10000000 > $SYSPATH/pwm4/duty_cycle 
  ;;
  *)
  
    ;;
  esac
}




main() {
  case "$1" in
  -h|--help)
    usage
    exit
    ;;
  enable)
    echo "Init motor and servo duty cycle"
    motor_crtl stop
    servo_crtl mid
    pwm_enable
    exit 1
    ;;
  disable)
    pwm_disable
    exit 1
    ;;
  motor)
    if [ ! -n "$2" ]; then
        usage
        exit 1
    fi
    motor_crtl $2 $3
    exit 1
    ;;
  servo)
    if [ ! -n "$2" ]; then
        usage
        exit 1
    fi
    servo_crtl $2
    exit 1
    ;;
  led)
    if [ ! -n "$2" ]; then
        usage
        exit 1
    fi
    led_pwm_ctrl $2
    exit 1
    ;;
  unexport)
    unexport_pwm_dev
    sleep 5
    exit 1
    ;;
  *)
    usage >&2
    exit 1
    ;;
  esac


}

main "$@"

public class simpleListToArraySize {

    public static int listArraySizeLeak(int h) {
        int ret;
        if (h < 10) {
            ret = h;
        } else {
            ret = 10;
        }
        return ret;
    }

}

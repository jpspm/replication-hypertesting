import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class Main {
	public static void main(String[] args) {
		int value = 5;
		int result = noLeak(value);
		Taint t = MultiTainter.getTaint(result);
		if (t != null) {
			System.out.println("Phosphor: ret is tainted");
			System.out.println("Phosphor: taint labels " + t);
		}
	}

  static long inThePast =  1456223086265L; // 23 Feb. 2016 11:24
	public static int noLeak(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
    long curr = System.currentTimeMillis() ;
    if (curr < inThePast) {
      ret = h;
        return ret;
    }
    ret = 0;
        return ret;
  }
}